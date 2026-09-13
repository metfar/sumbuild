# Retro digital clock for sumBASIC r21.1.
# Responsive text grid: big digits at 42+ columns, compact status otherwise.
# Q/q/Escape exits quickly; redraw/audio happen only when time/width changes.

DIM SHARED Font$(9, 6), Colon$(6)

FOR Digit! = 0 TO 9
    FOR Row! = 0 TO 6
        READ Font$(Digit!, Row!)
    NEXT Row!
NEXT Digit!

FOR Row! = 0 TO 6
    READ Colon$(Row!)
NEXT Row!

# Command-line tail example:
#   sumbasic --run retro_clock.bas --octava 5
Octave! = 2
IF ARGC > 0 THEN
    FOR ArgI! = 0 TO ARGC - 1
        Arg$ = LCASE$(ARGV$(ArgI!))
        IF (Arg$ = "--octava" OR Arg$ = "--octave" OR Arg$ = "-o") AND ArgI! + 1 < ARGC THEN
            Octave! = INT(VAL(ARGV$(ArgI! + 1)))
        END IF
    NEXT ArgI!
END IF
Octave! = MAX(0, MIN(6, Octave!))
Tick$ = "T240O" + STR$(Octave!) + "c"

OldT$ = ""
OldRows! = -1
OldCols! = -1
OldWide! = 99
VOLUME PLAY 25
CLS

:LOOP
T$ = TIME$
Cols! = COLS
Rows! = ROWS
Wide! = Cols! >= 42

# Crossing the 42-column threshold changes layout; clear only once then.
IF Wide! <> OldWide! THEN
    CLS
    OldWide! = Wide!
END IF

# Seconds or viewport width changed: repaint. Otherwise only poll input.
IF T$ <> OldT$ OR Cols! <> OldCols! OR Rows! <> OldRows! THEN
    CURSOR OFF
    IF Cols! <> OldCols! OR Rows! <> OldRows! THEN CLS
    Status$ = "TIME$=" + T$ + " TIMER=" + STR$(INT(TIMER)) + " O=" + STR$(Octave!) + "  Q=quit"

    IF Cols! < 42 OR Rows! < 13 THEN
        LOCATE 1, 1
        PRINT SPACE$(Cols!);
        LOCATE 1, 1
        PRINT LEFT$(Status$, Cols!);
    ELSE
        x = MAX(1, INT((Cols! - 42) / 2) + 1)
        ClearWidth! = MIN(64, Cols! - x + 1)

        FOR Row! = 0 TO 6
            Line$ = ""
            FOR Pos! = 1 TO 8
                C$ = MID$(T$, Pos!, 1)
                IF C$ = ":" THEN
                    Line$ = Line$ + Colon$(Row!) + " "
                ELSE
                    Digit! = VAL(C$)
                    Line$ = Line$ + Font$(Digit!, Row!) + " "
                END IF
            NEXT Pos!
            LOCATE Row! + 4, x: PRINT SPACE$(ClearWidth!);
            LOCATE Row! + 4, x: PRINT LEFT$(Line$, ClearWidth!);
        NEXT Row!

        LOCATE 13, x: PRINT SPACE$(ClearWidth!);
        LOCATE 13, x: PRINT LEFT$(Status$, ClearWidth!);
    END IF

    # Replace any previous background phrase before starting this tick.
    PLAY STOP
    PLAY BACKGROUND Tick$

    OldT$ = T$
    OldCols! = Cols!
    OldRows! = Rows!
    CURSOR ON
END IF

# A 50 ms ceiling keeps Q/Escape reaction fast. PAUSE preserves the wake key.
PAUSE .05
A$ = INKEY$
IF A$ = CHR$(27) OR A$ = "Q" OR A$ = "q" THEN END
IF A$ = "C" OR A$ = "c" THEN CLS
GOTO LOOP

# 0
DATA " ███ ", "█   █", "█  ██", "█ █ █", "██  █", "█   █", " ███ "
# 1
DATA "  █  ", " ██  ", "  █  ", "  █  ", "  █  ", "  █  ", "█████"
# 2
DATA " ███ ", "█   █", "    █", "   █ ", "  █  ", " █   ", "█████"
# 3
DATA "████ ", "    █", "    █", " ███ ", "    █", "    █", "████ "
# 4
DATA "█  █ ", "█  █ ", "█  █ ", "█████", "   █ ", "   █ ", "   █ "
# 5
DATA "█████", "█    ", "█    ", "████ ", "    █", "    █", "████ "
# 6
DATA " ███ ", "█    ", "█    ", "████ ", "█   █", "█   █", " ███ "
# 7
DATA "█████", "    █", "   █ ", "  █  ", " █   ", " █   ", " █   "
# 8
DATA " ███ ", "█   █", "█   █", " ███ ", "█   █", "█   █", " ███ "
# 9
DATA " ███ ", "█   █", "█   █", " ████", "    █", "    █", " ███ "
# colon
DATA "  ", "██", "██", "  ", "██", "██", "  "
