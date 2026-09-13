# Two historical sound models in the same educational BASIC.

PRINT "Spectrum BEEP: chromatic octave"
FOR Note! = 0 TO 12
    BEEP .08, Note!
NEXT Note!

PRINT "GW-BASIC SOUND: queued monophonic frequency sweep"
FOR Frequency! = 220 TO 880 STEP 55
    SOUND Frequency!, 1
NEXT Frequency!

# Approximately the same Middle C for about one second:
BEEP 1, 0
SOUND 262, 18.2

END
