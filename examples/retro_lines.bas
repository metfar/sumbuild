# Retro Lines - graphical sumBASIC demo.
# Two endpoints bounce independently around a 4:3 screen while the line
# joining them leaves a multicolour trail, like an old 1980s screensaver.
#
# Run:
#   sumbasic --gui --run examples/retro_lines.bas
#
# Escape, Q or q exits when run through the Sum GUI/IDE application.

SCREEN 320, 240
COLOR 7, 0, 0

X1 = 20:  Y1 = 30
X2 = 285: Y2 = 200
DX1 = 3:   DY1 = 2
DX2 = -2:  DY2 = 3
C = 1

:LOOP
INK C
LINE (X1, Y1)-(X2, Y2)

X1 = X1 + DX1: Y1 = Y1 + DY1
X2 = X2 + DX2: Y2 = Y2 + DY2

IF X1 <= 0 OR X1 >= 319 THEN DX1 = -DX1
IF Y1 <= 0 OR Y1 >= 239 THEN DY1 = -DY1
IF X2 <= 0 OR X2 >= 319 THEN DX2 = -DX2
IF Y2 <= 0 OR Y2 >= 239 THEN DY2 = -DY2

C = C + 1
IF C > 15 THEN C = 1

PAUSE .02
K$ = INKEY$
IF K$ = CHR$(27) OR K$ = "Q" OR K$ = "q" THEN SCREEN 0: END
GOTO LOOP
