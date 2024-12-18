import binaryninja
from binaryninja import (
    BinaryView, Type, StructureBuilder, Symbol, SymbolType, SegmentFlag,
    SectionSemantics, StructureType, StructureVariant, StructureMember, Settings
)
import threading
from .per_file_parser import *

def import_per(bv: BinaryView):
    """
    Imports peripherals from a Lauterbach .per file into Binary Ninja.

    Args:
        bv (BinaryView): The current BinaryView.
    """
    file_path = binaryninja.get_open_filename_input('Select .per File')
    cpu = binaryninja.get_text_line_input("CPU ID (reference .per file for more information or leave blank for all):", "CPU Input")
    if file_path is None:
        return
    binaryninja.log_info(f'Parsing .per file: {file_path}')

    task = binaryninja.BackgroundTask(f"Importing peripherals from {file_path}")

    def worker():
        parser = PerFileParser(file_path, cpu)
        parser.parse()

        show_comments = Settings().get_bool("PERMapper.enableComments")

        peripherals = {}
        for entry in parser.parsed_data:
            per_name = entry['tree'].strip(': ').split(':')[-1].strip()
            if per_name not in peripherals:
                peripherals[per_name] = {
                    'entries': [],
                    'base_address': entry['address'],
                    'description': '',
                }
            peripherals[per_name]['entries'].append(entry)

        total_peripherals = len(peripherals)
        current_peripheral = 0
        for per_name, per_data in peripherals.items():
            if task.cancelled:
                binaryninja.log_info('Peripheral import cancelled.')
                return
            
            current_peripheral += 1
            task.progress = (current_peripheral / total_peripherals) * 100

            entries = per_data['entries']
            base_address = min(entry['address'] for entry in entries)
            max_address = max(entry['address'] for entry in entries)
            per_size = max_address - base_address + 4  # Assuming 32-bit registers

            # Arbitrary limit, but if the importing script creates peripherials
            # too large binja can't save the file. Haven't figured out why it
            # messes up sometimes.
            if per_size > 1000000:
                binaryninja.log_error(f"Invalid Peripherial Size: {per_size} for peripherial: {per_name}. Skipping...")
                continue

            per_struct = StructureBuilder.create()

            for entry in entries:
                reg_name = entry['name']
                reg_offset = entry['address'] - base_address
                reg_type = Type.int(4, False)
                per_struct.insert(reg_offset, reg_type, reg_name)

                if show_comments:
                    bv.set_comment_at(entry['address'], f"{per_name}: {reg_name}")

            per_struct_name = per_name
            per_struct_type = Type.structure_type(per_struct)
            bv.define_user_type(per_struct_name, per_struct_type)

            def add_segment_and_section(per_name, base_address, per_size, per_struct_name):
                bv.add_user_segment(
                    base_address,
                    per_size,
                    0,
                    0,
                    SegmentFlag.SegmentReadable | SegmentFlag.SegmentWritable
                )
                bv.add_user_section(per_name, base_address, per_size, SectionSemantics.ReadWriteDataSectionSemantics)
                bv.memory_map.add_memory_region(per_name, base_address, bytearray(per_size))

                bv.define_user_data_var(base_address, bv.get_type_by_name(per_struct_name))
                bv.define_user_symbol(Symbol(SymbolType.ImportedDataSymbol, base_address, per_struct_name))
            try:
                action = binaryninja.execute_on_main_thread(lambda: add_segment_and_section(per_name, base_address, per_size, per_struct_name))
                action.wait()
            except Exception as e:
                binaryninja.log_info(e)
                continue
        
        binaryninja.log_info('Peripheral import completed.')
        task.finish()

    threading.Thread(target=worker).start()

settings = Settings()

comment_title = "Enable Comment Creation"
comment_description = "Create comments from the .per file entries"
comment_properties = (
    f'{{"title" : "{comment_title}", '
    f'"description" : "{comment_description}", '
    f'"type" : "boolean", "default" : true}}'
)

settings.register_group("PERMapper", "PER Mapper")
settings.register_setting("PERMapper.enableComments", comment_properties)

binaryninja.PluginCommand.register(
    "Import Lauterbach .per File",
    "Imports peripherals from a Lauterbach .per file into the BinaryView.",
    import_per
)