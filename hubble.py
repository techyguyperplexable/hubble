import usb.core
import usb.util
from colorama import just_fix_windows_console
import tarfile
import lz4.frame
import argparse
import struct
import sys
import os
from time import sleep

download_address = 0xFFFFFFFE

exynos9830_sboot_splits = [
    ["fwbl1.img", 0x0, 0x3000],
    ["epbl.img", 0x3000, 0x16000],
    ["bl2.img", 0x16000, 0x82000],
    ["lk.bin", 0xDB000, 0x35B000],
    ["el3_mon.img", 0x35B000, 0x39B000]
]

files_to_extract_tar = [
    "sboot.bin.lz4",
    "ldfw.img.lz4",
    "tzsw.img.lz4"
]

files_to_extract_lz4 = [
    "sboot.bin.lz4"
]

files_to_flash = [
    "ldfw.img.lz4",
    "tzsw.img.lz4"
]

OKAY = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
BLUE = '\033[94m'
CYAN = '\033[96m'
PURPLE = '\033[35m'
ENDC = '\033[0m'

def write_u32(value):
    return struct.pack('<I', value)

def write_header(data, address, size):
    data[:4] = write_u32(address)
    data[4:8] = write_u32(size)

def load_file(file_input):
    try:
        if isinstance(file_input, str):  # If input is a filename
            with open(file_input, 'rb') as file:
                file_data = file.read()
        elif isinstance(file_input, bytes):  # If input is raw bytes
            file_data = file_input
        else:
            raise TypeError("Invalid file input type. Must be filename (str) or raw data (bytes).")

        size = len(file_data) + 10
        block = bytearray(size)
        block[8:8+len(file_data)] = file_data

        return block
    except Exception as e:
        print(f"{FAIL}Error loading file: {e}{ENDC}")
        return None

def calculate_checksum(data):
    checksum = sum(data[8:-2]) & 0xFFFF
    print(f"{BLUE}=> Data checksum{ENDC} {OKAY}{checksum:04X}{ENDC}")
    data[-2:] = struct.pack('<H', checksum)

def find_device():
    usb_backend = None
    device_connection_attempts = 0

    if os.name == "nt":
        import usb.backend.libusb1
        import libusb

        usb_backend = usb.backend.libusb1.get_backend(find_library=lambda x: libusb.dll._name)

    while True:
        device = usb.core.find(idVendor=0x04e8, idProduct=0x1234, backend=usb_backend)

        if device is None:
            if device_connection_attempts == 15:
                device_connection_attempts = 0

                print()
                print(f"{CYAN}Tip: Plug in your device with the power button pressed.{ENDC}")

            print(".", end="", flush=True)
            device_connection_attempts += 1
            sleep(1)
        else:
            print()
            return device

def send_part_to_device(device, file, filename):
    file_size = len(file)

    print(f"{BLUE}=> Downloading{ENDC} {OKAY}{file_size}{ENDC} {BLUE}bytes to{ENDC} {OKAY}0x{download_address:08X}{ENDC}")

    write_header(file, download_address, file_size)
    calculate_checksum(file)

    ret = device.write(2, file, timeout=50000)
    print(f"{OKAY}=> {ret} bytes written.{ENDC}")
    print()

    if ret != file_size:
        print(f"{FAIL}Failed to write {file_size} bytes{ENDC}")
        sys.exit(-1)

def filter_tar(tarinfo, unused):
    if tarinfo.name in files_to_extract_tar:
        print(f"{OKAY}Extracted: {tarinfo.name}{ENDC}")
        return tarinfo
    return None

def extract_bl_tar(path):
    with tarfile.open(path, 'r') as tar:
        try:
            tar.extractall(path='.', members=tar.getmembers(), filter=filter_tar)
        except:
            print(f"{FAIL}Failure in extracting BL tar! Bailing!{ENDC}")
            sys.exit(-1)

    tar.close()

    for resultant_bin in files_to_extract_lz4:
        with open(resultant_bin, 'rb') as input_lz4:
            try:
                filename_no_lz4 = os.path.splitext(resultant_bin)[0]

                with open(filename_no_lz4, 'wb') as output_bin:
                    output_bin.write(lz4.frame.decompress(input_lz4.read()))

                    output_bin.close()

                print(f"{OKAY}Extracted: {filename_no_lz4}{ENDC}")
            except:
                print(f"{FAIL}Failure in extracting LZ4 archives! Bailing!{ENDC}")
                sys.exit(-1)

        input_lz4.close()

        try:
            delete_file(resultant_bin)
        except:
            print(f"{FAIL}Failure in preliminary cleanup! Bailing!{ENDC}")
            sys.exit(-1)

    print()

def delete_file(filename):
    os.remove(filename)
    print(f"{OKAY}Deleted: {filename}{ENDC}")

def display_and_verify_device_info(device):
    device_config = device.get_active_configuration()

    soc = usb.util.get_string(device, device.iProduct)
    usb_serial_num = usb.util.get_string(device, device.iSerialNumber)
    usb_booting_version = usb.util.get_string(device, device_config[(0, 0)].iInterface)

    print()
    print(f"{PURPLE}======== Device Information ========")
    print(f"         SoC:{ENDC} {OKAY}{soc}{ENDC}")
    print(f"         {PURPLE}SoC ID:{ENDC} {OKAY}{usb_serial_num[0:15]}{ENDC}")
    print(f"         {PURPLE}Chip ID:{ENDC} {OKAY}{usb_serial_num[15:31]}{ENDC}")
    print(f"         {PURPLE}USB Booting Version:{ENDC} {OKAY}{usb_booting_version[12:16]}{ENDC}")
    print()

    if soc != "Exynos9830\0":
        print(f"{FAIL}This isn't an exynos9830 device, backing out!{ENDC}")
        sys.exit(-1)

def main():
    just_fix_windows_console()

    print(rf"""{PURPLE}
  _    _ _    _ ____  ____  _      ______
 | |  | | |  | |  _ \|  _ \| |    |  ____|
 | |__| | |  | | |_) | |_) | |    | |__
 |  __  | |  | |  _ <|  _ <| |    |  __|
 | |  | | |__| | |_) | |_) | |____| |____
 |_|  |_|\____/|____/|____/|______|______|
{ENDC}""")

    print("USB Recovery Tool")
    print("Version 1.0 (c) 2025 Umer Uddin <umer.uddin@mentallysanemainliners.org>")
    print()
    print(f"{WARNING}Notice: This program and it's source code is licensed under GPL 2.0.")
    print()
    print(f"Notice: If you have paid for this, you have been{ENDC} {FAIL}scammed{ENDC}!")
    print(f"{WARNING}Please issue a refund and get the official program from{ENDC}")
    print(f"{CYAN}https://github.com/halal-beef/hubble-usb-recovery-tool{ENDC}")
    print()

    parser = argparse.ArgumentParser(description="USB Recovery Tool for Exynos9830 based devices.")
    parser.add_argument('-b', '--bl-tar', type=str, help="Path to the .tar or .tar.md5 file", required=True)

    args = parser.parse_args()

    if args.bl_tar:
        if os.path.isfile(args.bl_tar):
            print(f"{BLUE}Using file: {args.bl_tar}{ENDC}")
        else:
            print(f"{FAIL}Error: The file {args.bl_tar} does not exist or is not a valid file.{ENDC}")

    print(f"{BLUE}Extracting files...{ENDC}")
    print()
    extract_bl_tar(args.bl_tar)

    print(f"{BLUE}Waiting for device{ENDC}")
    device = find_device()
    print(f"{OKAY}Found device.{ENDC}")

    display_and_verify_device_info(device)

    print(f"{WARNING}Starting USB booting...{ENDC}")
    print()

    if os.name !="nt":
        if device.is_kernel_driver_active(0):
            device.detach_kernel_driver(0)

    usb.util.claim_interface(device, 0)

    with open("sboot.bin", "rb") as sboot:
        for sboot_split in exynos9830_sboot_splits:
            try:
                print(f"{WARNING}Sending file part {sboot_split[0]} (0x{sboot_split[1]:X} - 0x{sboot_split[2]:X})...{ENDC}")

                sboot.seek(sboot_split[1])
                sboot_section = load_file(sboot.read(sboot_split[2] - sboot_split[1]))

                if sboot_section is None:
                    print(f"{FAIL}Failed to load {sboot_split[0]}{ENDC}")
                    sys.exit(-1)

                send_part_to_device(device, sboot_section, sboot_split[0])
            except Exception as e:
                print(f"{FAIL}Error when trying to process sboot.bin. ({e}){ENDC}")
                sys.exit(-1)

        sboot.close()

    for download_file in files_to_flash:
        print(f"{WARNING}Sending file {download_file}...{ENDC}")

        download_data = load_file(download_file)

        if download_data is None:
            print(f"{FAIL}Failed to load {download_file}{ENDC}")
            sys.exit(-1)

        send_part_to_device(device, download_data, download_file)

    usb.util.release_interface(device, 0)
    usb.util.dispose_resources(device)

    print(f"{BLUE}Cleaning up...{ENDC}")
    print()

    try:
        for resultant_lz4 in files_to_flash:
            delete_file(resultant_lz4)

        for resultant_bin in files_to_extract_lz4:
            filename_no_lz4 = os.path.splitext(resultant_bin)[0]

            delete_file(filename_no_lz4)
    except:
        print(f"{FAIL}Failure in cleaning up! Bailing!{ENDC}")
        sys.exit(-1)

    print()
    print(f"{WARNING}You should be in download mode now, please reflash the stock firmware as the bootloader will still be wiped.{ENDC}")

if __name__ == "__main__":
    main()
