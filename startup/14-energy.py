from ophyd import (PseudoPositioner, PseudoSingle, EpicsMotor, Signal, EpicsSignalRO)
from ophyd import (Component as Cpt)
from ophyd.pseudopos import (pseudo_position_argument, real_position_argument)
from time import sleep

class MonoDCM(Device):
    bragg = Cpt(EpicsMotor, '-Ax:Bragg}Mtr')
    x = Cpt(EpicsMotor, '-Ax:X}Mtr')
    y = Cpt(EpicsMotor, '-Ax:Of2}Mtr')
    pitch2 = Cpt(EpicsMotor, '-Ax:P2}Mtr')
    roll2 = Cpt(EpicsMotor, '-Ax:R2}Mtr')
    fine_pitch = Cpt(EpicsMotor, '-Ax:PF2}Mtr')
    ccm_fine_pitch = Cpt(EpicsMotor, '-Ax:CCM_PF}Mtr')
    pitch2_rb = Cpt(EpicsSignalRO, '-Ax:PF_RDBK}Mtr.RBV')

mono = MonoDCM("XF:16IDA-OP{Mono:DCM", name="dcm")

# Calculate X-ray energy using the current theta position or from given argument    
def getE(bragg=None):
    # Si(111) lattice constant is 5.43095A
    d = 5.43095 
    # q = 2pi / d * sqrt(3.)
    # q = 4pi / lmd * sin(bragg)
    #
    try:
        lmd = 2.0/np.sqrt(3.)*d*np.sin(np.radians(bragg))
    except AttributeError:
        lmd = 2.0/np.sqrt(3.)*d*np.sin(np.radians(mono.bragg.position))
    energy = 1973.*2.*np.pi/lmd
    return energy

# Set energy to the given value, if calc_only=false otherwise only calculate
def setE(energy, calc_only=True, ov=-29.4153):
    # Si(111) lattice constant is 5.43095A
    d = 5.43095 
    offset = 20.0
    lmd = 1973.*2.*np.pi/energy
    bragg = np.degrees(np.arcsin(lmd*np.sqrt(3.)/(2.*d)))
    y0 = offset/(2.0*np.cos(np.radians(bragg)))
    if calc_only:
        print("expected Bragg angle is %.4f" % bragg)
        print("expected Y displacement is %.4f" % y0)
        print("expected Y motor position after correction is %.4f" % (y0+ov))
        print("run setE(%.1f,calc_only=False) to actually move the mono" % energy)
    else: # this actually moves the motors
        mono.bragg.move(bragg)
        mono.y.move(y0+ov)

def XBPM_pos(navg=5):
    xpos = 0.
    ypos = 0.
    px = PV('SR:C16-BI{XBPM:1}Pos:X-I')
    py = PV('SR:C16-BI{XBPM:1}Pos:Y-I')
    if px.connected==False or py.connected==False:
        return (np.nan, np.nan)
    try:
        for i in range(navg):
            xpos += caget('SR:C16-BI{XBPM:1}Pos:X-I')
            ypos += caget('SR:C16-BI{XBPM:1}Pos:Y-I')        
            sleep(0.05)
        return (xpos/navg, ypos/navg)
    except:
        return ("unknown", "unknown") 
        

# arcsec to radians conversion
def arcsec_rad(x):
    ## arcsec to rad conversion
    y=x*4.848136811097625
    print(y,"in radians")


# radians to arcsec conversion
def rad_arcsec(x):
    ## arcsec to rad conversion
    y=x/4.848136811097625
    print(y,"in arcsec")


class Energy(PseudoPositioner):
    # The pseudo positioner axes
    energy = Cpt(PseudoSingle, limits=(-100000, 100000))

    # The real (or physical) positioners:
    bragg = Cpt(EpicsMotor, 'XF:16IDA-OP{Mono:DCM-Ax:Bragg}Mtr')
    y = Cpt(EpicsMotor, 'XF:16IDA-OP{Mono:DCM-Ax:Of2}Mtr')
    #initial value=-28.5609
    # Variables
    ov = Cpt(Signal, value=-29.4153, 
             doc='ov is the correction needed to get actual Y value')
    
    @pseudo_position_argument
    def forward(self, target):
        '''Run a forward (pseudo -> real) calculation'''
        d = 5.43095
        offset = 20.0
        lmd = 1973.*2.*np.pi/target.energy
        brg = np.degrees(np.arcsin(lmd*np.sqrt(3.)/(2.*d)))
        y0 = offset/(2.0*np.cos(np.radians(brg)))
        y_calc = y0+self.ov.get()
        
        return self.RealPosition(bragg=brg, y=y_calc)

    @real_position_argument
    def inverse(self, real_pos):
        '''Run an inverse (real -> pseudo) calculation'''
        # Si(111) lattice constant is 5.43095A
        d = 5.43095
        # q = 2pi / d * sqrt(3.)
        # q = 4pi / lmd * sin(bragg)
        #
        lmd = 2.0/np.sqrt(3.)*d*np.sin(np.radians(real_pos.bragg))
        calc_energy = 1973.*2.*np.pi/lmd
        return self.PseudoPosition(energy=calc_energy)


pseudo_energy = Energy('', name='energy')
energy = pseudo_energy.energy
