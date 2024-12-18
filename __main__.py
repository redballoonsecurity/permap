import sys
from per_file_parser import PerFileParser

if __name__ == '__main__':
    file_path = sys.argv[1]
    if len(sys.argv) > 2:
        cpu = sys.argv[2]
    else:
        cpu = ""
    
    if not file_path:
        print('Please provide a .per file!')
    else:
        print(f'Parsing .per file... {file_path[0]}')
        parser = PerFileParser(file_path, cpu)
        parser.parse()
        
        if not parser.parsed_data:
            print('No data found in the .per file.')
        else:
            peripherals = {}
            for entry in parser.parsed_data:
                per_name = entry['tree'].strip(': ').split(':')[-1].strip()
                if per_name not in peripherals:
                    peripherals[per_name] = {
                        'base_address': entry['address'],
                        'entries': []
                    }
                peripherals[per_name]['entries'].append(entry)
            for per_name, per_data in peripherals.items():
                base_address = per_data['base_address']
                print(f'Peripheral: {per_name} @ {hex(base_address)}')
                entries = per_data['entries']
                base_address = min(entry['address'] for entry in entries)
                max_address = max(entry['address'] for entry in entries)
                per_size = max_address - base_address + 4  # Assuming 32-bit registers
                print(f"Persize: {per_size}")
                for entry in per_data['entries']:
                    reg_name = entry['name']
                    reg_address = entry['address']
                    print(f'    Register: {reg_name} @ {hex(reg_address)}')