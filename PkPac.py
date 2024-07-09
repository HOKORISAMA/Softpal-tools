import os
import struct
import sys
from typing import List, Tuple

class Entry:
    def __init__(self, name: str, size: int, offset: int):
        self.name = name
        self.size = size
        self.offset = offset

class PacPacker:
    def __init__(self):
        self.name_length = 0x20  # Using the longer name length option

    def pack(self, input_dir: str, output_file: str):
        entries = self.collect_files(input_dir)
        self.write_archive(entries, input_dir, output_file)

    def collect_files(self, input_dir: str) -> List[Entry]:
        entries = []
        offset = 0x3FE + len(os.listdir(input_dir)) * (self.name_length + 8)  # Start of file data

        for filename in os.listdir(input_dir):
            filepath = os.path.join(input_dir, filename)
            if os.path.isfile(filepath):
                size = os.path.getsize(filepath)
                entry = Entry(filename, size, offset)
                entries.append(entry)
                offset += size

        return entries

    def write_archive(self, entries: List[Entry], input_dir: str, output_file: str):
        with open(output_file, 'wb') as f:
            # Write file count
            f.write(struct.pack('<I', len(entries)))
            
            # Pad until index start
            f.write(b'\0' * (0x3FE - 4))

            # Write index
            for entry in entries:
                name_bytes = entry.name.encode('ascii')
                f.write(name_bytes.ljust(self.name_length, b'\0'))
                f.write(struct.pack('<II', entry.size, entry.offset))

            # Write file data
            for entry in entries:
                filepath = os.path.join(input_dir, entry.name)
                with open(filepath, 'rb') as input_file:
                    data = input_file.read()
                    
                # Apply encryption if needed
                if entry.name.split('.')[-1].lower() not in ['jpg', 'png', 'bmp', 'wav', 'mp3'] and len(data) > 16:
                    data = self.encrypt_data(data)
                
                f.write(data)

    def encrypt_data(self, data: bytes) -> bytes:
        if data[0] != ord('$'):
            return data

        data_array = bytearray(data)
        count = (len(data) - 16) // 4
        if count > 0:
            shift = 4
            for i in range(16, len(data_array), 4):
                value = struct.unpack('<I', data_array[i:i+4])[0]
                value ^= 0x084DF873 ^ 0xFF987DEE
                struct.pack_into('<I', data_array, i, value)
                data_array[i] = (data_array[i] >> shift) | (data_array[i] << (8 - shift)) & 0xFF
                shift += 1
                if shift > 7:
                    shift = 0

        return bytes(data_array)

def pack_archive(input_dir: str, output_file: str):
    packer = PacPacker()
    packer.pack(input_dir, output_file)
    print(f"Archive created: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: Pkpac.py <input_directory> <output_archive>")
        sys.exit(1)

    input_directory = sys.argv[1]
    output_archive = sys.argv[2]

    pack_archive(input_directory, output_archive)
