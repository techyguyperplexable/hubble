import usb.core
import usb.util
import tarfile
import lz4.frame
import argparse
import struct
import sys
import os
from time import sleep

download_address = 0xfffffffe

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
        print(f"Error loading file: {e}")
        return None

def calculate_checksum(data):
    checksum = sum(data[8:-2]) & 0xFFFF
    print(f"=> Data checksum {checksum:04X}")
    data[-2:] = struct.pack('<H', checksum)

def find_device():
    device_connection_attempts = 0

    while True:
        device = usb.core.find(idVendor=0x04e8, idProduct=0x1234)

        if device is None:
            if device_connection_attempts == 15:
                device_connection_attempts = 0
                print()
                print("Tip: Plug in your device with the power button pressed.")

            print(".", end="", flush=True)
            device_connection_attempts += 1
            sleep(1)
        else:
            print()
            return device

def filter_tar(tarinfo, unused):
    if tarinfo.name in files_to_extract_tar:
        print(f"Extracted: {tarinfo.name}")
        return tarinfo
    return None

def main():
    print(r"""
  _    _ _    _ ____  ____  _      ______
 | |  | | |  | |  _ \|  _ \| |    |  ____|
 | |__| | |  | | |_) | |_) | |    | |__
 |  __  | |  | |  _ <|  _ <| |    |  __|
 | |  | | |__| | |_) | |_) | |____| |____
 |_|  |_|\____/|____/|____/|______|______|
""")

    print("USB Recovery Tool")
    print("Version 1.0 (c) 2025 Umer Uddin <umer.uddin@mentallysanemainliners.org>")
    print()
    print("Notice: This program and it's source code is licensed under GPL 2.0.")
    print()
    print("Notice: If you have paid for this, you have been scammed!")
    print("Please issue a refund and get the official program from")
    print("https://github.com/halal-beef/hubble-usb-recovery-tool")
    print()

    parser = argparse.ArgumentParser(description="USB Recovery Tool for Exynos9830 based devices.")
    parser.add_argument('-b', '--bl-tar', type=str, help="Path to the .tar or .tar.md5 file", required=True)

    args = parser.parse_args()

    if args.bl_tar:
        if os.path.isfile(args.bl_tar):
            print(f"Using file: {args.bl_tar}")
        else:
            print(f"Error: The file {args.bl_tar} does not exist or is not a valid file.")

    print("Extracting files...")
    print()

    with tarfile.open(args.bl_tar, 'r') as tar:
        try:
            tar.extractall(path='.', members=tar.getmembers(), filter=filter_tar)
        except:
            print("Failure in extracting BL tar! Bailing!")
            sys.exit(1)

    tar.close()

    for resultant_bin in files_to_extract_lz4:
        with open(resultant_bin, 'rb') as input_lz4:
            try:
                filename_no_lz4 = os.path.splitext(resultant_bin)[0]

                with open(filename_no_lz4, 'wb') as output_bin:
                    output_bin.write(lz4.frame.decompress(input_lz4.read()))

                    output_bin.close()

                print(f"Extracted: {filename_no_lz4}")
            except:
                print("Failure in extracting LZ4 archives! Bailing!")
                sys.exit(1)

        input_lz4.close()

        try:
            os.remove(resultant_bin)
            print(f"Deleted: {resultant_bin}")
        except:
            print("Failure in preliminary cleanup! Bailing!")
            sys.exit(1)

    print()

    print("Waiting for device")

    device = find_device()
    device_config = device.get_active_configuration()

    print("Found device.")

    soc = usb.util.get_string(device, device.iProduct)
    usb_serial_num = usb.util.get_string(device, device.iSerialNumber)
    usb_booting_version = usb.util.get_string(device, device_config[(0, 0)].iInterface)

    print()
    print("======== Device Information ========")
    print(f"         SoC: {soc}")
    print(f"         SoC ID: {usb_serial_num[0:15]}")
    print(f"         Chip ID: {usb_serial_num[15:31]}")
    print(f"         USB Booting Version: {usb_booting_version[12:16]}")
    print()

    if soc != "Exynos9830\0":
        print("This isn't an exynos9830 device, backing out!")
        sys.exit(-1)

    print("Starting USB booting...")

    if device.is_kernel_driver_active(0):
        device.detach_kernel_driver(0)
    usb.util.claim_interface(device, 0)

    print()

    with open("sboot.bin", "rb") as sboot:
        for sboot_split in exynos9830_sboot_splits:
            try:
                print(f"Sending file part {sboot_split[0]} (0x{sboot_split[1]:X} - 0x{sboot_split[2]:X})...")
                sboot.seek(sboot_split[1])
                sboot_section = load_file(sboot.read(sboot_split[2] - sboot_split[1]))
                sboot_section_length = len(sboot_section)

                if sboot_section is None:
                    print(f"Failed to load {sboot_split[0]}")
                    sys.exit(1)

                print(f"=> Downloading {sboot_section_length} bytes to 0x{download_address:08x}")
                write_header(sboot_section, download_address, sboot_section_length)
                calculate_checksum(sboot_section)

                ret = device.write(2, sboot_section, timeout=50000)
                print(f"=> {ret} bytes written.")
                print()

                if ret != sboot_section_length:
                    print(f"Failed to write {sboot_section_length} bytes")
                    sys.exit(-1)
            except Exception as e:
                print(f"Error when trying to process or send sboot.bin parts. ({e})")
                sys.exit(1)

        sboot.close()

    for download_file in files_to_flash:
        print(f"Sending file part {download_file}...")
        download_data = load_file(download_file)
        download_data_length = len(download_data)

        if download_data is None:
            print(f"Failed to load {download_file}")
            sys.exit(1)

        print(f"=> Downloading {download_data_length} bytes to 0x{download_address:08x}")
        write_header(download_data, download_address, download_data_length)
        calculate_checksum(download_data)

        ret = device.write(2, download_data, timeout=50000)
        print(f"=> {ret} bytes written.")
        print()

        if ret != download_data_length:
            print(f"Failed to write {download_data_length} bytes")
            sys.exit(-1)

    usb.util.release_interface(device, 0)
    usb.util.dispose_resources(device)

    print("Cleaning up...")

    try:
        for resultant_lz4 in files_to_flash:
            os.remove(resultant_lz4)
            print(f"Deleted: {resultant_lz4}")

        for resultant_bin in files_to_extract_lz4:
            filename_no_lz4 = os.path.splitext(resultant_bin)[0]

            os.remove(filename_no_lz4)
            print(f"Deleted: {filename_no_lz4}")
    except:
        print("Failure in cleaning up! Bailing!")
        sys.exit(1)

    print()

    print("You should be in download mode now, please reflash the stock firmware as the bootloader will still be wiped.")

if __name__ == "__main__":
    main()
