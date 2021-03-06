import re
import argparse


__all__ = ["GlasgowAppletError", "GlasgowApplet", "GlasgowAppletTestCase",
           "synthesis_test", "applet_simulation_test"]


class GlasgowAppletError(Exception):
    """An exception raised when an applet encounters an error."""


class GlasgowApplet:
    all_applets = {}

    def __init_subclass__(cls, name, **kwargs):
        super().__init_subclass__(**kwargs)

        if name in cls.all_applets:
            raise ValueError("Applet {!r} already exists".format(name))

        cls.all_applets[name] = cls
        cls.name = name

    @classmethod
    def add_build_arguments(cls, parser, access):
        access.add_build_arguments(parser)

    def build(self, target):
        raise NotImplemented

    @classmethod
    def add_run_arguments(cls, parser, access):
        access.add_run_arguments(parser)

    async def run(self, device, args):
        raise NotImplemented

    @classmethod
    def add_interact_arguments(cls, parser):
        pass

    async def interact(self, device, args, interface):
        pass

# -------------------------------------------------------------------------------------------------

import os
import shutil
import unittest
import functools
from migen.sim import *

from ..access.direct import *
from ..access.simulation import *
from ..target.hardware import *
from ..target.simulation import *
from ..device.simulation import *


class GlasgowAppletTestCase(unittest.TestCase):
    def __init_subclass__(cls, applet, **kwargs):
        super().__init_subclass__(**kwargs)

        applet.test_cls = cls
        cls.applet_cls  = applet

    def setUp(self):
        self.applet = self.applet_cls()

    def assertBuilds(self, access="direct", args=[]):
        if access == "direct":
            target = GlasgowHardwareTarget(multiplexer_cls=DirectMultiplexer)
            access_args = DirectArguments(applet_name=self.applet.name,
                                          default_port="A", pin_count=8)
        else:
            raise NotImplementedError

        parser = argparse.ArgumentParser()
        self.applet.add_build_arguments(parser, access_args)

        parsed_args = parser.parse_args(args)
        self.applet.build(target, parsed_args)

        target.get_bitstream(debug=True)

    def _prepare_simulation_target(self, args):
        self.target = GlasgowSimulationTarget()
        self.target.submodules.multiplexer = SimulationMultiplexer()

        self.device = GlasgowSimulationDevice()
        self.device.demultiplexer = SimulationDemultiplexer(self.device)

        access_args = SimulationArguments(applet_name=self.applet.name)

        parser = argparse.ArgumentParser()
        self.applet.add_build_arguments(parser, access_args)
        self.applet.add_run_arguments(parser, access_args)

        self._parsed_args = parser.parse_args(args)

    def build_simulated_applet(self):
        self.applet.build(self.target, self._parsed_args)

    async def run_simulated_applet(self):
        return await self.applet.run(self.device, self._parsed_args)


def synthesis_test(case):
    synthesis_available = (shutil.which("yosys") is not None and
                           shutil.which("arachne-pnr") is not None)

    return unittest.skipUnless(synthesis_available, "synthesis not available")(case)


def applet_simulation_test(setup, args=[]):
    def decorator(case):
        @functools.wraps(case)
        def wrapper(self):
            self._prepare_simulation_target(args)
            getattr(self, setup)()
            vcd_name = "{}.vcd".format(case.__name__)
            run_simulation(self.target, case(self), vcd_name=vcd_name)
            os.remove(vcd_name)

        return wrapper

    return decorator

# -------------------------------------------------------------------------------------------------

from .rgb_grabber import RGBGrabberApplet
from .hd44780 import HD44780Applet
from .i2c_master import I2CMasterApplet
from .i2c.bmp280 import I2CBMP280Applet
from .i2c.eeprom_24c import I2CEEPROM24CApplet
from .program_ice40 import ProgramICE40Applet
from .selftest import SelfTestApplet
from .uart import UARTApplet
