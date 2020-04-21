# -*- coding:utf-8 -*-

# Octowire Framework
# Copyright (c) Jordan Ovrè / Paul Duncan
# License: GPLv3
# Paul Duncan / Eresse <eresse@dooba.io>
# Jordan Ovrè / Ghecko <ghecko78@gmail.com

import codecs
import shutil
import struct
import time

from octowire_framework.module.AModule import AModule
from octowire.gpio import GPIO
from octowire.spi import SPI


class FlashWrite(AModule):
    def __init__(self, owf_config):
        super(FlashWrite, self).__init__(owf_config)
        self.meta.update({
            'name': 'SPI write flash',
            'version': '1.0.0',
            'description': 'Module to write an SPI flash',
            'author': 'Jordan Ovrè <ghecko78@gmail.com> / Paul Duncan <eresse@dooba.io>'
        })
        self.options = [
            {"Name": "spi_bus", "Value": "", "Required": True, "Type": "int",
             "Description": "The octowire SPI device (0=SPI0 or 1=SPI1)", "Default": 0},
            {"Name": "cs_pin", "Value": "", "Required": True, "Type": "int",
             "Description": "The octowire GPIO used as chip select (CS)", "Default": 0},
            {"Name": "firmware", "Value": "", "Required": True, "Type": "file_r",
             "Description": "The firmware to write to the SPI flash memory", "Default": ""},
            {"Name": "start_chunk", "Value": "", "Required": True, "Type": "int",
             "Description": "The starting chunk address (1 chunk = 256 bytes)", "Default": 0},
            {"Name": "spi_baudrate", "Value": "", "Required": True, "Type": "int",
             "Description": "set SPI baudrate (1000000 = 1MHz) maximum = 50MHz", "Default": 1000000},
            {"Name": "spi_polarity", "Value": "", "Required": True, "Type": "int",
             "Description": "set SPI polarity (1=high or 0=low)", "Default": 0},
            {"Name": "spi_phase", "Value": "", "Required": True, "Type": "string",
             "Description": "set SPI phase (1=high or 0=low)", "Default": 0}
        ]
        self.advanced_options.append(
            {"Name": "chunk_size", "Value": "", "Required": True, "Type": "int",
             "Description": "Flash page/sector size", "Default": 0x0100}
        )
        self.t_width, _ = shutil.get_terminal_size()

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
            print(" " * self.t_width, end="\r", flush=True)
            print('Erasing status : 0x{}'.format(codecs.encode(status, 'hex').decode()), end="\r", flush=True)
            time.sleep(0.01)
        print(" " * self.t_width, end="\r", flush=True)
        cs.status = 1

    def write_flash(self, spi_instance, cs, data, addr):
        self.write_enable(spi_instance, cs)
        cs.status = 0
        spi_instance.transmit(b"\x02" + (struct.pack(">L", addr)[1:]))
        spi_instance.transmit(data)
        cs.status = 1
        self.wait_status(spi_instance, cs)

    def writing_process(self):
        bus_id = self.get_option_value("spi_bus")
        cs_pin = self.get_option_value("cs_pin")
        spi_baudrate = self.get_option_value("spi_baudrate")
        spi_cpol = self.get_option_value("spi_polarity")
        spi_cpha = self.get_option_value("spi_phase")
        current_chunk_addr = self.get_option_value("start_chunk")
        firmware = self.get_option_value("firmware")
        chunk_size = self.get_advanced_option_value("chunk_size")

        t_width, _ = shutil.get_terminal_size()

        # Set and configure the GPIO interface used as chip select
        cs = GPIO(serial_instance=self.owf_serial, gpio_pin=cs_pin)
        cs.direction = GPIO.OUTPUT
        cs.status = 1

        # Set and configure SPI interface
        flash_interface = SPI(serial_instance=self.owf_serial, bus_id=bus_id)
        flash_interface.configure(baudrate=spi_baudrate, clock_polarity=spi_cpol, clock_phase=spi_cpha)
        try:
            self.write_enable(flash_interface, cs)
            self.logger.handle("Erasing flash...", self.logger.INFO)
            self.erase(flash_interface, cs)
            self.logger.handle("Writing to flash...", self.logger.INFO)
            with open(firmware, "rb") as f:
                while data := f.read(chunk_size):
                    print(" " * t_width, end="\r", flush=True)
                    print("[*] Writing to address: {}".format(hex(current_chunk_addr)), end="\r", flush=True)
                    self.write_flash(flash_interface, cs, data, current_chunk_addr)
                    current_chunk_addr += chunk_size
                self.logger.handle("Done!", self.logger.SUCCESS)
        except (Exception, ValueError) as err:
            self.logger.handle(err, self.logger.ERROR)

    def run(self):
        """
        Main function.
        The aim of this module is to write an spi flash.
        :return:
        """
        # If detect_octowire is True then Detect and connect to the Octowire hardware. Else, connect to the Octowire
        # using the parameters that were configured. It sets the self.owf_serial variable if the hardware is found.
        self.connect()
        if not self.owf_serial:
            return
        self.writing_process()

