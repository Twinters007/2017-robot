import wpilib
import math

from networktables import NetworkTable
from networktables.util import ntproperty


MAX_VOLTAGE = 5
MAX_TICK = 4096
MAX_DEG = 360

WHEEL_DIAMETER = 4/12  # 4 Inches
WHEEL_CIRCUMFERENCE = WHEEL_DIAMETER * math.pi

# FIXME: Make this number more accurate. I'd bet my life that it's not exactly 55,000
WHEEL_TICKS_PER_REV = 55_000


class SwerveModule:

    def __init__(self, *args, **kwargs):
        """
        Swerve drive module was written for a swerve drive train that uses absolute encoders for tracking wheel rotation.

        When positional arguments are used:
            :param driveMotor: Motor object
            :param rotateMotor: Motor object
            :param encoder: AnalogInput wpilib object

        When key word arguments are used:
            :param encoderPort: analog in port number of Absolute Encoder

            :param SDPrefix: a string used to differentiate modules when debugging
            :param zero: The default zero for the encoder
            :param inverted: boolean to invert the wheel rotation

            :param allow_reverse: If true allows wheels to spin backwards instead of rotating
            :param has_drive_encoder: If true allows the module to track wheel position

        """

        # SmartDashboard
        self.sd = NetworkTable.getTable('SmartDashboard')
        self.sd_prefix = kwargs.pop('SDPrefix', False)

        # Motors
        self.driveMotor = args[0]
        self.drive_inverted = kwargs.pop('inverted', False)
        self.driveMotor.setInverted(self.drive_inverted)

        self.rotateMotor = args[1]

        self._requested_voltage = 0  # Angle in voltage form
        self._requested_speed = 0

        # Encoder
        self.encoder = args[2]
        self.encoder_zero = kwargs.pop('zero', 0.0)

        # PID
        self._pid_controller = wpilib.PIDController(1.5, 0.0, 0.0, self.encoder, self.rotateMotor)
        self._pid_controller.setContinuous()
        self._pid_controller.setInputRange(0.0, 5.0)
        self._pid_controller.enable()

        # State variables
        self.allow_reverse = kwargs.pop('allow_reverse', True)
        self.debugging = self.sd.getAutoUpdateValue('drive/%s/debugging' % self.sd_prefix, False)

        self.has_drive_encoder = kwargs.pop('has_drive_encoder', False)

    def set_pid(self, p, i, d):
        self._pid_controller.setPID(p, i, d)

    def get_voltage(self):
        """
        :return: the voltage position after the zero.
        """
        return self.encoder.getAverageVoltage() - self.encoder_zero

    def get_drive_encoder_tick(self):
        """
        :return: the positional value of the drive encoder
        """
        if not self.has_drive_encoder:
            return False

        return self.driveMotor.getPosition()

    def get_drive_encoder_distance(self):
        """
        :return: distance the wheel has rotated in feet.
        """
        if not self.has_drive_encoder:
            return False

        return ((self.driveMotor.getPosition()) * WHEEL_CIRCUMFERENCE) / WHEEL_TICKS_PER_REV

    def flush(self):
        """
        Flushes the modules requested speed and voltage
        """
        self._requested_voltage = self.encoder.getVoltage()
        self._requested_speed = 0

    @staticmethod
    def voltage_to_degrees(voltage):
        """
        Convert a given voltage value to degrees

        :param voltage: a voltage value between 0 and 5
        """

        deg = (voltage/5)*360
        deg = deg

        if deg < 0:
            deg = 360+deg;

        return deg

    @staticmethod
    def voltage_to_rad(voltage):
        """
        Convert a given voltage value to rad

        :param voltage: a voltage value between 0 and 5
        """

        rad = (voltage/5)*2*math.pi
        return rad

    @staticmethod
    def voltage_to_tick(voltage):
        """
        Convert a given voltage value to tick

        :param voltage: a voltage value between 0 and 5
        """

        # FIXME: This shouldn't be 4050. In fact it should be a reference to the constant
        return (voltage/5)*4050

    @staticmethod
    def degree_to_voltage(degree):
        """
        Convert a given degree to voltage

        :param degree: a degree value between 0 and 360
        """

        return (degree/360)*5

    @staticmethod
    def tick_to_voltage(tick):
        """
        Convert a given tick to voltage

        :param tick: a tick value between 0 and 4050
        """

        # FIXME: This shouldn't be 4050. In face it should be a reference to the constant
        return (tick/4050)*5

    def zero_encoder(self):
        """
        Set the zero to the current voltage output
        """

        self.encoder_zero = self.encoder.getVoltage()

    def is_aligned(self):
        """
        :return: True if wheel is aligned to set point (False if not)
        """
        if abs(self._pid_controller.getError()) < 0.1:
            return True
        return False

    def _set_deg(self, value):
        """
        Round the value to within 360. Set the requested rotate position (requested voltage).
        Intended to be used only by the move function.
        """

        self._requested_voltage = ((self.degree_to_voltage(value)+self.encoder_zero) % 5)

    def move(self, speed, deg):
        """
        Set the requested speed and rotation of passed.
        
        :param speed: requested speed of wheel from -1 to 1
        :param deg: requested angle of wheel from 0 to 359 (Will wrap if over or under)
        """
        deg %= 360  # Prevent values past 360

        if self.allow_reverse:
            if abs( deg - self.voltage_to_degrees(self.get_voltage()) ) > 90:
                speed *= -1
                deg += 180

                deg = deg % 360

        self._requested_speed = speed
        self._set_deg(deg)

    def debug(self):
        """
        Prints debugging information about the module to the log.
        """
        print(self.sd_prefix, '; requested_speed: ', self._requested_speed, ' requested_voltage: ', self._requested_voltage)

    def execute(self):
        """
        Use the PID controller to get closer to the requested position.
        Set the speed requested of the drive motor.

        Should be called every robot iteration/loop.
        """

        self._pid_controller.setSetpoint(self._requested_voltage)
        self.driveMotor.set(self._requested_speed)

        self._requested_speed = 0.0

        self.update_smartdash()

    def update_smartdash(self):
        """
        Output a bunch on internal variables for debugging purposes.
        """

        self.sd.putNumber('drive/%s/degrees' % self.sd_prefix, self.voltage_to_degrees(self.get_voltage()))

        if self.has_drive_encoder:
            self.sd.putNumber('drive/%s/raw drive position' % self.sd_prefix, self.driveMotor.getPosition())

        if self.debugging.value:
            self.sd.putNumber('drive/%s/requested_voltage' % self.sd_prefix, self._requested_voltage)
            self.sd.putNumber('drive/%s/requested_speed' % self.sd_prefix, self._requested_speed)
            self.sd.putNumber('drive/%s/raw voltage' % self.sd_prefix, self.encoder.getVoltage())  # DO NOT USE self.get_voltage() here
            self.sd.putNumber('drive/%s/average voltage' % self.sd_prefix, self.encoder.getAverageVoltage())
            self.sd.putNumber('drive/%s/encoder_zero' % self.sd_prefix, self.encoder_zero)

            self.sd.putNumber('drive/%s/PID' % self.sd_prefix, self._pid_controller.get())
            self.sd.putNumber('drive/%s/PID Error' % self.sd_prefix, self._pid_controller.getError())

            self.sd.putBoolean('drive/%s/allow_reverse' % self.sd_prefix, self.allow_reverse)
