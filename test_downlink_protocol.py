from archive.payload_manager_helper import BATCH_SIZE, CHUNK_SIZE
from ccsds_packet import CCSDS_Chunk_Packet, CCSDS_Control_Packet
import subprocess
import serial
import pprint
import os


# TEST_FILEPATH = '/home/pi/Desktop/Mission/2021-04-19_09:57:00
TEST_FILEPATH = '/home/pi/Desktop/test'

#### DOWNLINK CONSTANTS ####
BATCH_SIZE = 5
PRE_ENC_CHUNK_SIZE = 120  # bytes, w/o 16 bytes rs encoding yet
TELEMETRY_PACKET_TYPE_DOWNLINK_START = 30
TELEMETRY_PACKET_TYPE_DOWNLINK_PACKET = 31
TELEMETRY_PACKET_TYPE_DOWNLINK_STOP = 32


# Given mission folder path, obtain list of images path
def obtain_downlink_images_filepaths(mission_folder_path):
    list_filepaths = []
    for file in os.listdir(mission_folder_path):
        list_filepaths.append(mission_folder_path + '/' + file)
    return list_filepaths


# Given filepath to image, compress and encode the image bytes and return the bytes
def extract_enc_img_bytes(img_filepath):
    # Grant permission to script if not already done so
    os.chmod("prep_test.sh", 0o777)
    os.chmod("cleanup.sh", 0o777)

    # Call bash script to execute prep script
    # base64 + gzip
    prep_filepath = './prep_test.sh ' + img_filepath
    subprocess.call(prep_filepath, stdout=subprocess.DEVNULL, shell=True)

    # Open and read in the image
    with open('base_enc.gz', 'rb') as file:
        compressed_enc = file.read()
        file.close()

    # Call bash script to remove currently created compressed files
    subprocess.call('./cleanup.sh base_enc.gz',
                    stdout=subprocess.DEVNULL, shell=True)

    return compressed_enc


def prepare_tx_batch(enc_img_bytes):

    # Returns a list of chunks of bytes, given chunk size and bytearray
    def chop_bytes(bytes_arr, chunk_size):
        chunk_arr = []
        idx = 0
        while idx + chunk_size < len(bytes_arr):
            chunk_arr.append(bytes_arr[idx:idx + chunk_size])
            idx = idx + chunk_size
        # Remaining odd sized chunk
        chunk_arr.append(bytes_arr[idx:])
        return chunk_arr

    # Given an list of chunks, split them into list of batches given a batch size
    def split_batch(chunks_arr, batch_size):
        batch_arr = []
        idx = 0
        while idx + batch_size <= len(chunks_arr):
            batch_arr.append(chunks_arr[idx:idx + batch_size])
            idx = idx + batch_size
        # Remaining odd sized chunk
        batch_arr.append(chunks_arr[idx:])
        return batch_arr

    # Chop up bytes into chunks and prepare CCSDS packet
    chunk_list = chop_bytes(enc_img_bytes, PRE_ENC_CHUNK_SIZE)

    # Split chunks into batches
    batch_list = split_batch(chunk_list, BATCH_SIZE)

    # Create CCSDS Packets
    packet_batch_list = []
    packet_seq_num = 1
    for batch_num in range(len(batch_list)):
        batch = batch_list[batch_num]

        chunk_num = 1
        new_batch = []
        for chunk in batch:
            # Create CCSDS Packet for each chunk
            packet = CCSDS_Chunk_Packet(
                packet_seq_num, TELEMETRY_PACKET_TYPE_DOWNLINK_PACKET, batch_num+1, chunk_num, chunk)
            new_batch.append(packet)
            packet_seq_num += 1
            chunk_num += 1

        # Put stop packet
        stop_packet = CCSDS_Control_Packet(
            packet_seq_num, TELEMETRY_PACKET_TYPE_DOWNLINK_STOP, 0, 0)
        new_batch.append(stop_packet)
        packet_seq_num += 1

        packet_batch_list.append(new_batch)

    return packet_batch_list


def main():
    ser_downlink = serial.Serial("/dev/ttyUSB0", baudrate=115200, timeout=10)

    # Get list of files to downlink
    filepath_list = obtain_downlink_images_filepaths(TEST_FILEPATH)
    pprint.pprint(filepath_list)  # Print list of files for debug

    # Handle downlink of each image
    total_img_num = len(filepath_list)
    for filepath in filepath_list:
        enc_img_bytes = extract_enc_img_bytes(filepath)
        batches = prepare_tx_batch(enc_img_bytes)

        print((batches[0])[0].get_tx_packet())


if __name__ == "__main__":
    main()
