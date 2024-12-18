import binaryninja
import re


import re

class PerFileParser:
    """
    A parser for Lauterbach .per files to extract peripheral mappings
    and generate a Binary Ninja script.
    """

    def __init__(self, filename: str, cpu: str):
        """
        Initializes the parser with the given .per file.

        Args:
            filename (str): The path to the .per file to parse.
        """
        self.filename = filename
        self.base_addr = None
        self.lines = []
        self.tree_stack = []
        self.parsed_data = []
        self.cpu = cpu
        # State variables to handle nesting
        # Each entry in this stack will be a tuple:
        # (already_matched_in_this_block, should_consider)
        # "already_matched_in_this_block": True if a previous sif/elif in the same block has already matched and chosen lines
        # "should_consider": True if we are currently inside a chosen block of code
        self.condition_stack = []
        self.should_consider = True


    def parse(self):
        """
        Parses the .per file and extracts mapped entries.
        """
        with open(self.filename, 'r') as f:
            self.lines = [line.strip() for line in f]

        for index, line in enumerate(self.lines):
            # If statements and conditionals do not apply to lines containing tree or base addr
            self._parse_tree_name(line)
            self._parse_base_addr(line)
            stripped = line.strip()
            if stripped.startswith('sif '):
                # Starting a new conditional block
                cond_str = stripped[4:].strip()
                # Push a new state
                cond_result = self.evaluate_condition(cond_str, self.cpu)
                # When we enter a sif, no previous match in this block, so:
                self.condition_stack.append((cond_result, cond_result))
                self.should_consider = self.should_consider and cond_result
            elif stripped.startswith('elif '):
                cond_str = stripped[5:].strip()
                # We are continuing in the same block, so look at the top of the stack
                if self.condition_stack:
                    already_matched, _ = self.condition_stack.pop()
                    if already_matched:
                        # If already matched some previous sif/elif, this elif won't match
                        # Re-push with same already_matched = True, self.should_print = False
                        self.condition_stack.append((True, False))
                        self.should_consider = False
                    else:
                        # No previous match, evaluate this
                        cond_result = self.evaluate_condition(cond_str, self.cpu)
                        # If this matches, set already_matched = True, else False
                        self.condition_stack.append((cond_result, cond_result))
                        self.should_consider = cond_result
            elif stripped.startswith('else'):
                # if no conditions matched so far
                if self.condition_stack:
                    already_matched, _ = self.condition_stack.pop()
                    if already_matched:
                        # Already matched, so else is skipped
                        self.condition_stack.append((True, False))
                        self.should_consider = False
                    else:
                        # No match yet, else block executes
                        self.condition_stack.append((True, True))
                        self.should_consider = True
            elif stripped.startswith('endif'):
                # End of current block
                if self.condition_stack:
                    self.condition_stack.pop()
                # Determine self.should_consider based on what's left on the stack
                self.should_consider = True
                for am, sc in self.condition_stack:
                    # If any upper block is false, we can't print
                    self.should_consider = self.should_consider and sc
            else:
                # Normal line
                if self.should_consider:
                    mapped_entry = self._parse_mapped_name(index, line)
                    if mapped_entry:
                        self.parsed_data.append(mapped_entry)

    def _parse_tree_name(self, line: str):
        """
        Parses tree names and updates the tree stack.

        Args:
            line (str): The current line from the .per file.
        """
        if line.startswith("tree"):
            if "tree.end" in line:
                if self.tree_stack:
                    self.tree_stack.pop()
            else:
                match = re.match(r'tree\s+"([^"]+)"', line)
                if match:
                    tree_name = match.group(1)
                    self.tree_stack.append(tree_name)

    def _parse_base_addr(self, line: str):
        """
        Parses the base addr and updates the class variable.

        Args:
            line: The current line from the .per file.
        """
        match  = re.match(
            r'base.*(0x[0-9A-Fa-f]+)',
            line
        )
        if match:
            self.base_addr, = match.groups()

    def _parse_mapped_name(self, index, line):
        """
        Parses mapped names and returns a dictionary with the extracted data.

        Args:
            index (int): The current line index.
            line (str): The current line from the .per file.

        Returns:
            dict or None: A dictionary with the parsed data or None if parsing fails.
        """
        match = re.match(
            r'group.(?P<type>\w+) \(?(?P<baseAddr>0x[0-9A-Fa-f]+)*?\+?(?P<offset>[\.x:a-fA-F0-9]+)\)?\+\+(?:0x[A-Fa-f0-9]+)( \"(?P<name>[^\"]+)\")?',
            line
        )
        if match:
            captures = match.groupdict()
            name = ""
            if not captures["name"]:
                # Look ahead to the next line for the name
                if index + 1 < len(self.lines):
                    name_match = re.match(
                        r'line.(?:\w+)\s+[xa-fA-F0-9]+ \"(.+)\"',
                        self.lines[index + 1]
                    )
                    if name_match:
                        name, = name_match.groups()
            else:
                name = captures["name"]
            baseAddr = captures["baseAddr"] if captures["baseAddr"] else self.base_addr
            if name: # On rare occation name will still be none at this point. Might just be an error in the .per file.
                offset = captures["offset"]
                if not baseAddr: # If baseAddr is still none we can assume that the offset is just the base addr
                    baseAddr = offset
                    offset = "0x0"
                _, _, offset = offset.rpartition(":")
                _, _, baseAddr = baseAddr.rpartition(":")
                name = name.strip()
                return self._create_mapped_entry(captures["type"], baseAddr, offset, name)
        return None

    def _create_mapped_entry(self, _type, _address, _offset, _name):
        """
        Creates a mapped entry dictionary from the extracted data.

        Args:
            _type (str): The type extracted from the .per file.
            _address (str): The base address as a string.
            _offset (str): The offset as a string.
            _name (str): The name of the peripheral.

        Returns:
            dict or None: A dictionary with the mapped entry or None if address is invalid.
        """
        address = self._calculate_address(_address, _offset)
        tree_name = ": ".join(self.tree_stack) + ": " if self.tree_stack else ""
        if address:
            return {
                'address': address,
                'type': _type,
                'name': _name,
                'tree': tree_name,
            }
        else:
            return None

    def _calculate_address(self, base_address: str, offset: str):
        """
        Calculates the actual address from the base address and offset.

        Args:
            base_address (str): The base address as a string.
            offset (str): The offset as a string.

        Returns:
            int or None: The calculated address or None if calculation fails.
        """
        try:
            if offset.startswith("0x"):
                return int(base_address, 16) + int(offset, 16)
            elif "." in offset:
                # Remove trailing dot and convert to integer
                return int(base_address, 16) + int(offset.rstrip('.'), 10)
            else:
                # Assume decimal offset
                return int(base_address, 16) + int(offset, 10)
        except ValueError as e:
            binaryninja.log_error(f"Error calculating address: {e}")
            return None
        
    
    # Helper function to evaluate a condition of form (cpu()=="LPCXXX"||cpu()=="LPCYYY") etc.
    def evaluate_condition(self, cond_str, cpu):
        # cond_str looks like: (cpu()=="LPC2880"||cpu()=="LPC2888") etc.
        # We'll extract all cpu names from it and check if any match.
        
        # A simple regex to find occurrences of cpu()=="XYZ"
        matches = re.findall(r'cpu\(\)==\"([A-Za-z0-9/]+)\"', cond_str)
        # Check OR conditions:
        # If the line has ||, then we return True if any matches
        # If it had &&, would need more complex logic.
        if cpu == "": # User didn't enter a CPU
            return True
        for m in matches:
            if m == cpu:
                return True
        
        return False