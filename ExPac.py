import os
import struct
from typing import List, Optional
from abc import ABC, abstractmethod

class Entry:
    def __init__(self, name: str):
        self.name = name
        self.size: int = 0
        self.offset: int = 0
        self.type: str = self.determine_type()

    def determine_type(self) -> str:
        ext = os.path.splitext(self.name)[1].lower()
        if ext in ['.BPIC', '.pgd', '.PIC']:
            return 'image'
        elif ext in ['.wav', '.ogg']:
            return 'audio'
        else:
            return 'unknown'

class ArchiveFormat(ABC):
    @property
    @abstractmethod
    def try_open(self, file_path: str) -> Optional[List[Entry]]:
        pass

class PacOpener(ArchiveFormat):

    def try_open(self, file_path: str) -> Optional[List[Entry]]:
        with open(file_path, 'rb') as file:
            count = struct.unpack('<I', file.read(4))[0]
            if not self.is_sane_count(count):
                return None

            index_offset = 0x3FE
            name_length = 0x20
            file.seek(index_offset + name_length + 4)
            first_offset = struct.unpack('<I', file.read(4))[0]

            if first_offset != index_offset + count * (name_length + 8):
                name_length = 0x10
                file.seek(index_offset + name_length + 4)
                first_offset = struct.unpack('<I', file.read(4))[0]
                if first_offset != index_offset + count * (name_length + 8):
                    return None

            return self.read_index(file, count, index_offset, name_length)

    @staticmethod
    def is_sane_count(count: int) -> bool:
        return 0 < count < 100000  # Arbitrary sanity check

    @staticmethod
    def read_index(file, count: int, index_offset: int, name_length: int) -> List[Entry]:
        entries = []
        for _ in range(count):
            file.seek(index_offset)
            name = file.read(name_length).decode('ascii').rstrip('\0')
            index_offset += name_length
            file.seek(index_offset)
            size, offset = struct.unpack('<II', file.read(8))
            entry = Entry(name)
            entry.size = size
            entry.offset = offset
            entries.append(entry)
            index_offset += 8
        return entries

    def open_entry(self, file_path: str, entry: Entry) -> bytes:
        with open(file_path, 'rb') as file:
            file.seek(entry.offset)
            data = file.read(entry.size)

        if entry.type in ['image', 'audio'] or entry.size <= 16 or data[0] != ord('$'):
            return data

        count = (len(data) - 16) // 4
        if count > 0:
            data_array = bytearray(data)
            shift = 4
            for i in range(16, len(data_array), 4):
                data_array[i] = (data_array[i] << shift) & 0xFF | (data_array[i] >> (8 - shift))
                shift += 1
                if shift > 7:
                    shift = 0
                value = struct.unpack('<I', data_array[i:i+4])[0]
                value ^= 0x084DF873 ^ 0xFF987DEE
                struct.pack_into('<I', data_array, i, value)
            data = bytes(data_array)

        return data

class Pac2Opener(PacOpener):
    @property
    def signature(self) -> int:
        return 0x20434150  # 'PAC '

    def try_open(self, file_path: str) -> Optional[List[Entry]]:
        with open(file_path, 'rb') as file:
            file.seek(8)
            count = struct.unpack('<I', file.read(4))[0]
            if not self.is_sane_count(count):
                return None

            index_offset = 0x804
            name_length = 0x20
            file.seek(index_offset + name_length + 4)
            first_offset = struct.unpack('<I', file.read(4))[0]
            if first_offset != index_offset + count * (name_length + 8):
                return None

            return self.read_index(file, count, index_offset, name_length)

def extract_archive(archive_path: str, output_dir: str):
    openers = [PacOpener(), Pac2Opener()]
    entries = None

    for opener in openers:
        entries = opener.try_open(archive_path)
        if entries:
            break

    if entries is None:
        print(f"Failed to open archive: {archive_path}")
        return

    os.makedirs(output_dir, exist_ok=True)

    for entry in entries:
        output_path = os.path.join(output_dir, entry.name)
        print(f"Extracting: {entry.name}")
        data = opener.open_entry(archive_path, entry)
        with open(output_path, 'wb') as out_file:
            out_file.write(data)

    print(f"Extraction complete. Files saved to: {output_dir}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python script.py <archive_file> <output_directory>")
        sys.exit(1)

    archive_file = sys.argv[1]
    output_directory = sys.argv[2]

    extract_archive(archive_file, output_directory)
