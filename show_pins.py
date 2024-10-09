
import Jetson.GPIO as GPIO
from Jetson.GPIO.gpio_pin_data import JETSON_ORIN_NX_PIN_DEFS


keys = ("linux_gpio", "linux_exported_gpio", "chip", "BOARD", "BCM", "CVM", "TEGRA","pwm_chip_sysfs", "pwm_id")
d = {}

data = [dict(zip(keys, p)) for p in JETSON_ORIN_NX_PIN_DEFS]

for row in data:
    print(f"BOARD: {row['BOARD']}\tBCM: {row['BCM']}\tTEGRA: {row['CVM']}\tpwm: {row['pwm_id']}")


"""
board: 7, BCM: 4, TEGRA: GP167
board: 11, BCM: 17, TEGRA: GP72_UART1_RTS_N
board: 12, BCM: 18, TEGRA: GP122
board: 13, BCM: 27, TEGRA: GP36_SPI3_CLK
board: 15, BCM: 22, TEGRA: GP88_PWM1
board: 16, BCM: 23, TEGRA: GP40_SPI3_CS1_N
board: 18, BCM: 24, TEGRA: GP39_SPI3_CS0_N
board: 19, BCM: 10, TEGRA: GP49_SPI1_MOSI
board: 21, BCM: 9, TEGRA: GP48_SPI1_MISO
board: 22, BCM: 25, TEGRA: GP37_SPI3_MISO
board: 23, BCM: 11, TEGRA: GP47_SPI1_CLK
board: 24, BCM: 8, TEGRA: GP50_SPI1_CS0_N
board: 26, BCM: 7, TEGRA: GP51_SPI1_CS1_N
board: 29, BCM: 5, TEGRA: GP65
board: 31, BCM: 6, TEGRA: GP66
board: 32, BCM: 12, TEGRA: GP113_PWM7
board: 33, BCM: 13, TEGRA: GP115
board: 35, BCM: 19, TEGRA: GP125
board: 36, BCM: 16, TEGRA: GP73_UART1_CTS_N
board: 37, BCM: 26, TEGRA: GP38_SPI3_MOSI
board: 38, BCM: 20, TEGRA: GP124
board: 40, BCM: 21, TEGRA: GP123
"""