from migen import *

from .target.hardware import GlasgowHardwareTarget


__all__ = ["TestToggleIO", "TestMirrorI2C", "TestShiftOut", "TestGenSeq", "TestPLL",
           "TestRegisters"]


class TestToggleIO(GlasgowHardwareTarget):
    def __init__(self):
        super().__init__()

        cnt = Signal(max=15000, reset=15000)
        out = Signal()
        self.sync += [
            cnt.eq(cnt - 1),
            If(cnt == 0,
                cnt.eq(cnt.reset),
                out.eq(~out)
            )
        ]

        self.comb += [
            self.platform.request("sync").eq(out),
            self.platform.request("io").eq(Replicate(out, 8)),
            self.platform.request("io").eq(Replicate(out, 8)),
        ]


class TestMirrorI2C(GlasgowHardwareTarget):
    def __init__(self):
        super().__init__()

        i2c = self.i2c_slave.bus
        self.comb += [
            self.platform.request("io").eq(Cat(i2c.scl_i, i2c.sda_i))
        ]


class TestShiftOut(GlasgowHardwareTarget):
    def __init__(self, is_async=False):
        super().__init__()

        if is_async:
            div = Signal(3)
            clk = Signal()
            self.sync.sys += [
                div.eq(div - 1),
                If(div == 0, clk.eq(~clk))
            ]

            self.clock_domains.cd_shift = ClockDomain()
            self.comb += self.cd_shift.clk.eq(clk)

            domain = "shift"
            out = self.fx2_arbiter.get_out_fifo(0, clock_domain=self.cd_shift)
        else:
            domain = "sys"
            out = self.fx2_arbiter.get_out_fifo(0)

        sck = Signal(reset=1)
        sdo = Signal()
        self.comb += [
            self.platform.request("io").eq(Cat(sck, sdo))
        ]

        shreg = Signal(8)
        bitno = Signal(3)
        self.submodules.fsm = ClockDomainsRenamer(domain)(FSM(reset_state="IDLE"))
        self.fsm.act("IDLE",
            If(out.readable,
                out.re.eq(1),
                NextValue(bitno, 7),
                NextValue(shreg, out.dout),
                NextState("SETUP")
            )
        )
        self.fsm.act("SETUP",
            NextValue(sck, 0),
            NextValue(sdo, shreg[7]),
            NextState("HOLD")
        )
        self.fsm.act("HOLD",
            NextValue(sck, 1),
            NextValue(bitno, bitno - 1),
            NextValue(shreg, shreg << 1),
            If(bitno != 0,
                NextState("SETUP")
            ).Else(
                NextState("IDLE")
            )
        )


class TestGenSeq(GlasgowHardwareTarget):
    def __init__(self):
        super().__init__()

        out0 = self.fx2_arbiter.get_out_fifo(0)
        in0 = self.fx2_arbiter.get_in_fifo(0)
        in1 = self.fx2_arbiter.get_in_fifo(1)

        stb = Signal()
        re  = Signal()
        self.sync += [
            out0.re.eq(out0.readable),
            re.eq(out0.re),
            stb.eq(out0.re & ~re)
        ]

        act = Signal()
        nam = Signal()
        cnt = Signal(8)
        lim = Signal(8)
        self.sync += [
            If(stb,
                act.eq(1),
                nam.eq(1),
                lim.eq(out0.dout),
                cnt.eq(0),
            ),
            If(act,
                nam.eq(~nam),
                in0.we.eq(1),
                in1.we.eq(1),
                If(nam,
                    in0.din.eq(b'A'[0]),
                    in1.din.eq(b'B'[0]),
                ).Else(
                    in0.din.eq(cnt),
                    in1.din.eq(cnt),
                    cnt.eq(cnt + 1),
                    If(cnt + 1 == lim,
                        act.eq(0)
                    )
                ),
            ).Else(
                in0.we.eq(0),
                in1.we.eq(0),
            ),
        ]


class TestPLL(GlasgowHardwareTarget):
    def __init__(self):
        super().__init__()

        self.specials += \
            Instance("SB_PLL40_CORE",
                p_FEEDBACK_PATH="SIMPLE",
                p_PLLOUT_SELECT="GENCLK",
                p_DIVR=0,
                p_DIVF=31,
                p_DIVQ=6,
                p_FILTER_RANGE=1,
                i_REFERENCECLK=ClockSignal(),
                o_PLLOUTCORE=self.platform.request("sync"),
                i_RESETB=1,
                i_BYPASS=0,
            )

        cnt = Signal()


class TestRegisters(GlasgowHardwareTarget):
    def __init__(self):
        super().__init__()

        reg_i, addr_i = self.registers.add_rw(8)
        reg_o, addr_o = self.registers.add_ro(8)

        self.comb += reg_o.eq(reg_i << 1)
