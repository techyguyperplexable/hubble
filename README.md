# Hubble - A USB Recovery Tool for devices based on Exynos9830

## Why?
 - Why not?
 - I don't want people to be paying to unbrick their devices

## How do I use it?
 - Setup UDEV Rules (I don't have a guide for this, yet, if you dont know how, just run the tool with sudo)
 - Install required python packages via ```pip3 install -r requirements.txt```
 - Run the tool, pointing to your bootloader tar file via ```python3 hubble.py -b <PATH_TO_BL_TAR>```
 - Plug in your bricked phone
 - Let it run it's magic
 - Reflash the stock firmware

## Supported devices

 > [!Warning]
 > This tool is strictly for devices based on Exynos9830!

 - [ ] Means your device is most likely supported but not tested
 - [x] Means your device is supported and tested

>

 - [x] Samsung Galaxy S20 (x1s/lte)
 - [x] Samsung Galaxy S20 Ultra (z3s/lte)
 - [ ] Samsung Galaxy S20+ (y2s/lte)
 - [ ] Samsung Galaxy S20 FE (r8s)
 - [ ] Samsung Galaxy Note20 (c1s/lte)
 - [ ] Samsung Galaxy Note20 Ultra (c2s/lte)

## Credits
 - [VDavid003](https://github.com/vdavid003) ```Helped me get the BL2 split on the bootloader```
 - [gaitenis](https://xdaforums.com/m/gaitenis.13049039) ```Finding lk.bin split```
 - [halal-beef](https://github.com/halal-beef) ```Initial idea, writing the tool and getting most of the splits```
 - [BotchedRPR](https://github.com/BotchedRPR) ```Loads of support and bricked his S20 Ultra for testing splits, absolute legend```
