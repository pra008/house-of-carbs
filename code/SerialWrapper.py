import serial
import time
import sys
import glob


class SerialWrapper:
    def __init__(self, device, cols, rows):
        self.ser = serial.Serial(device, 9600, timeout=1)
        self.matrixwritecommand([0xD1, cols, rows])
        self.matrixwritecommand([0x58])

    def close(self):
        self.ser.close()

    def matrixwritecommand(self, commandlist):
        commandlist.insert(0, 0xFE)
        for i in range(0, len(commandlist)):
            self.ser.write(bytearray(commandlist))

    def write_text(self, text):
        """ This function translate the string into char to be display """
        for line in text.split('\n'):
            self.ser.write(line.encode())
            self.new_line()

    def set_light_intensity(self, value):
        """
        This function set the intensity of the light
        works with value from 0 to 255
        0 -> minimum intensity
        255 -> maximum intensity
        :param value:
        :return:
        """
        self.matrixwritecommand([0x99, value])
        
    def light_on(self):
        """ This function turns on the display light """
        self.matrixwritecommand([0x42, 0x0])

    def light_off(self):
        """ This function turns off the display light """
        self.matrixwritecommand([0x46])

    def cls(self):
        """ This function clears the screen """
        self.matrixwritecommand([0x58])

    def light_white(self):
        """ This function resets the light """
        self.matrixwritecommand([0xD0, 0xFF, 0xFF, 0xFF])

    def light_black(self):
        """ This function makes no light """
        self.matrixwritecommand([0xD0, 0x0, 0x0, 0x0])

    def light_red(self):
        """ This function set the light to red """
        self.matrixwritecommand([0xD0, 0xFF, 0x0, 0x0])

    def light_green(self):
        """ This function set the light to green """
        self.matrixwritecommand([0xD0, 0x0, 0xFF, 0x0])

    def light_blue(self):
        """ This function set the light to blue """
        self.matrixwritecommand([0xD0, 0x0, 0x0, 0xFF])
        
    def light_purple(self):
        self.matrixwritecommand([0xD0, 0x4B, 0x00, 0x82])

    def light_rgb(self, red, green, blue):
        """ This function set the light using the RGB components"""
        self.matrixwritecommand([0xD0, red, green, blue])
        
    def new_line(self):
        """
        This function put the cursor in the beginning of the second row
        :return:
        """
        self.matrixwritecommand([0x47, 1, 2])


if __name__ == '__main__':
    d = SerialWrapper('COM11', 16, 2)
    d.light_on()

    # hypo
    d.write_text("BG=3.5 mmol/L\n1 min ago DOSE")
    d.set_light_intensity(255)
    d.light_red()
    time.sleep(10)
    # in range
    d.cls()
    d.write_text("BG=6.5 mmol/L\n2 min ago")
    d.set_light_intensity(253)
    d.light_green()
    time.sleep(10)
    # hyper
    d.cls()
    d.write_text("BG=11.5 mmol/L\n6 min ago")
    d.set_light_intensity(245)
    d.light_rgb(0x4B,0x0,0x82)
    #d.light_purple()
    time.sleep(10)
    # recent
    d.cls()
    d.write_text("BG=5.5 mmol/L\n1 min ago")
    d.light_green()
    d.set_light_intensity(255)
    time.sleep(10)
    # 16 minutes
    d.cls()
    d.write_text("BG=5.5 mmol/L\n16 min ago")
    d.light_green()
    d.set_light_intensity(95)
    time.sleep(10)
    # 16 minutes
    d.cls()
    d.write_text("BG=5.5 mmol/L\n1 hr ago")
    d.light_green()
    d.set_light_intensity(2)
    time.sleep(10)

    d.close()



    


