10 REM TABLICA
20 PRINT "*** ТАБЛИЦА УМНОЖЕНИЯ ***"
30 FOR V01 = 1 TO 9
40 PRINT "СКОЛЬКО БУДЕТ 7 *";V01
50 INPUT V02
60 V03 = V01 * 7
70 IF V02 = V03 GOTO 100
80 PRINT "НЕТ, БУДЕТ";V03
90 GOTO 110
100 PRINT "ВЕРНО"
110 NEXT V01
120 PRINT "*** КОНЕЦ ***"
130 END
