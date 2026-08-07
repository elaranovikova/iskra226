10 REM UGADAY
20 PRINT "*** УГАДАЙ ЧИСЛО ***"
30 PRINT "Я ЗАГАДАЛ ЧИСЛО ОТ 1 ДО 99"
40 V01 = 37
50 V02 = 0
60 PRINT "ВАШ ОТВЕТ"
70 INPUT V03
80 V02 = V02 + 1
90 IF V03 = V01 GOTO 200
100 IF V03 > V01 GOTO 150
110 PRINT "БОЛЬШЕ"
120 GOTO 60
150 PRINT "МЕНЬШЕ"
160 GOTO 60
200 PRINT "ВЕРНО! ПОПЫТОК";V02
210 END
