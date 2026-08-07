10 REM CHAT TERMINAL
20 PRINT "*** ИСКРА-226 - ТЕРМИНАЛ СВЯЗИ ***"
30 PRINT "ЛИНИЯ 015 - СПРАВОЧНАЯ СИСТЕМА"
40 PRINT "ПРОЕКТ: ЭМУЛЯЦИЯ ИСКРЫ-226"
50 PRINT "ВВЕДИТЕ ВОПРОС. ПУСТАЯ СТРОКА - КОНЕЦ."
60 PRINT
100 V10 = V10 + 1
110 PRINT "--- ЗАПРОС";V10
120 INPUT V01
130 IF V01 = "" GOTO 900
140 IF V01 = "КОНЕЦ" GOTO 900
150 SELECT PRINT 015
160 PRINT V01
170 SELECT PRINT 005
180 PRINT
190 PRINT "ОТВЕТ:"
200 INPUT V02
210 IF V02 = "." GOTO 300
220 PRINT V02
230 GOTO 200
300 PRINT
310 GOTO 100
900 PRINT "*** СВЯЗЬ ЗАВЕРШЕНА ***"
910 END
