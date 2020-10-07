# -*- coding: utf-8 -*-

# Octowire Framework
# Copyright (c) ImmunIT - Jordan Ovrè / Paul Duncan
# License: Apache 2.0
# Paul Duncan / Eresse <pduncan@immunit.ch>
# Jordan Ovrè / Ghecko <jovre@immunit.ch>

import math
import os
import shutil
import struct
import time

from tqdm import tqdm

from octowire_framework.module.AModule import AModule
from octowire.gpio import GPIO
from octowire.spi import SPI


class FlashWrite(AModule):
    def __init__(self, owf_config):
        super(FlashWrite, self).__init__(owf_config)
        self.meta.update({
            'name': 'SPI flash write',
            'version': '1.1.0',
            'description': 'Program generic SPI flash memories',
            'author': 'Jordan Ovrè / Ghecko <jovre@immunit.ch>, Paul Duncan / Eresse <pduncan@immunit.ch>'
        })
        self.options = {
            "spi_bus": {"Value": "", "Required": True, "Type": "int",
                        "Description": "SPI bus (0=SPI0 or 1=SPI1)", "Default": 0},
            "cs_pin": {"Value": "", "Required": True, "Type": "int",
                       "Description": "GPIO used as chip select (CS)", "Default": 0},
            "firmware": {"Value": "", "Required": True, "Type": "file_r",
                         "Description": "Firmware file to write into the SPI flash memory", "Default": ""},
            "start_chunk": {"Value": "", "Required": True, "Type": "int",
                            "Description": "Starting chunk (page) address (1 chunk = 256 bytes)", "Default": 0},
            "spi_baudrate": {"Value": "", "Required": True, "Type": "int",
                             "Description": "SPI frequency (1000000 = 1MHz) maximum = 50MHz", "Default": 1000000},
            "spi_polarity": {"Value": "", "Required": True, "Type": "int",
                             "Description": "SPI polarity (1=high or 0=low)", "Default": 0},
            "spi_phase": {"Value": "", "Required": True, "Type": "string",
                          "Description": "SPI phase (1=high or 0=low)", "Default": 0}
        }
        self.advanced_options.update({
            "chunk_size": {"Value": "", "Required": True, "Type": "int",
                           "Description": "Flash page size", "Default": 256}
        })
        self.t_width, _ = shutil.get_terminal_size()

    @staticmethod
    def _sizeof_fmt(num, suffix='B'):
        for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
            if abs(num) < 1024.0:
                return "%3.1f%s%s" % (num, unit, suffix)
            num /= 1024.0
        return "%.1f%s%s" % (num, 'Yi', suffix)

    @staticmethod
    def write_enable(spi_instance, cs):
        cs.status = 0
        spi_instance.transmit(b"\x06")
        cs.status = 1

    def erase(self, spi_instance, cs):
        cs.status = 0
        spi_instance.transmit(b"\xc7")
        cs.status = 1
        self.wait_status(spi_instance, cs)
        self.logger.handle("Done!", self.logger.SUCCESS)

    def wait_status(self, spi_instance, cs):
        cs.status = 0
        spi_instance.transmit(b"\x05")
        status = spi_instance.receive(1)
        while status != b"\x00":
            status = spi_instance.receive(1)
            time.sleep(0.01)
        cs.status = 1

    def write_flash(self, spi_instance, cs, data, addr):
        self.write_enable(spi_instance, cs)
        cs.status = 0
        spi_instance.transmit(b"\x02" + (struct.pack(">L", addr)[1:]))
        spi_instance.transmit(data)
        cs.status = 1
        self.wait_status(spi_instance, cs)

    def writing_process(self):
        bus_id = self.options["spi_bus"]["Value"]
        cs_pin = self.options["cs_pin"]["Value"]
        spi_baudrate = self.options["spi_baudrate"]["Value"]
        spi_cpol = self.options["spi_polarity"]["Value"]
        spi_cpha = self.options["spi_phase"]["Value"]
        start_chunk_addr = self.options["start_chunk"]["Value"]
        firmware = self.options["firmware"]["Value"]
        chunk_size = self.advanced_options["chunk_size"]["Value"]

        firmware_size = os.stat(firmware).st_size
        nb_of_chunks = math.ceil(firmware_size / chunk_size)

        t_width, _ = shutil.get_terminal_size()

        # Setup and configure the GPIO interface used as chip select
        cs = GPIO(serial_instance=self.owf_serial, gpio_pin=cs_pin)
        cs.direction = GPIO.OUTPUT
        cs.status = 1

        # Setup and configure SPI interface
        flash_interface = SPI(serial_instance=self.owf_serial, bus_id=bus_id)
        flash_interface.configure(baudrate=spi_baudrate, clock_polarity=spi_cpol, clock_phase=spi_cpha)
        try:
            self.write_enable(flash_interface, cs)
            self.logger.handle("Erasing flash...", self.logger.INFO)
            self.erase(flash_interface, cs)
            self.logger.handle("Writing {} bytes to the flash memory...".format(firmware_size), self.logger.INFO)
            with open(firmware, "rb") as f:
                for sector_nb in tqdm(range(start_chunk_addr, nb_of_chunks), desc="Reading",
                                      unit_scale=False, ascii=" #", unit_divisor=1,
                                      bar_format="{desc} : {percentage:3.0f}%[{bar}] {n_fmt}/{total_fmt} "
                                                 "pages (" + str(chunk_size) + " bytes) "
                                                 "[elapsed: {elapsed} left: {remaining}]"):
                    chunk_addr = sector_nb * chunk_size
                    data = f.read(chunk_size)
                    self.write_flash(flash_interface, cs, data, chunk_addr)
            self.logger.handle("Successfully write {} to flash memory.".format(self._sizeof_fmt(firmware_size)),
                               self.logger.SUCCESS)
        except (Exception, ValueError) as err:
            self.logger.handle(err, self.logger.ERROR)

    def run(self):
        """
        Main function.
        Program generic SPI flash memories.
        :return:
        """
        # If detect_octowire is True then detect and connect to the Octowire hardware. Else, connect to the Octowire
        # using the parameters that were configured. This sets the self.owf_serial variable if the hardware is found.
        self.connect()
        if not self.owf_serial:
            return
        self.writing_process()

