# sumBASIC BGI-style drawing demo over the common Sum graphics layer.
# No .BGI driver files are used.
DISPLAY 640,480,65536,AUTO
COLOR 15,1,1
CLS

# Cyan face on blue background; deliberately no yellow-on-black palette.
CIRCLE 320,210,90,11
PAINT (320,210),3,11
CIRCLE 285,185,12,15
PAINT (285,185),15,15
CIRCLE 355,185,12,15
PAINT (355,185),15,15
ARC 320,220,220,320,55,15
OUTTEXTXY 205,345,"sumBASIC / Sum BGI-style graphics",15,16,"monospace"

BSAVE "bgi_style_smile.png", SCREEN
PAUSE 5
SCREEN 0
