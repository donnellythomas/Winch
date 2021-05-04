#!/usr/bin/env python3

try:
    # for Python2
    import Tkinter  as tk
except ImportError:
    # for Python3
    import tkinter as tk
import tkinter.font as tkFont
import time
import RPi.GPIO as GPIO



#Wheel diameter in mm
WheelDiameter = 101
WheelCircumference = WheelDiameter * 3.141592654

#how many count in moving average
dynamicMovingAverageMaxCount=8

WheelSensorGPIO=  21


class App():


   def __init__(self):
       self.dynamicMovingAverage= [0] * (dynamicMovingAverageMaxCount +1)
       self.dynamicMovingAverageCount=0
       self.sensorTimer=0
       self.root = tk.Tk()
       self.root.wm_title('Cyclo meter')
       self.deci=0
       self.odometerValue=0.0
       self.speedValue=0.0
       self.speedFrame(self.root)
       self.timerFrame(self.root)
       self.odometerFrame(self.root)
       self.avgSpeedFrame(self.root)
#       self.settingsFrame(self.root)
       self.resetFrame(self.root)
       self.startTime=time.time()
       self.update_clock()



   def mainloop(self):
       self.root.mainloop()


   def subFrame(self,mFrame,Title):
       sFrame = tk.Frame(mFrame)
       sFrame.pack(side= tk.TOP,fill=tk.X)
       tFrame = tk.Frame(sFrame)
       tFrame.pack(side=tk.TOP,fill=tk.X)
       lFrame = tk.Frame(tFrame)
       lFrame.pack(side=tk.LEFT,fill=tk.X)
       titleLabel = tk.Label(lFrame,text=Title)
       titleLabel.pack(side=tk.LEFT)
       aFrame = tk.Frame(sFrame)
       aFrame.pack(side=tk.TOP,fill=tk.X)
       self.separator(sFrame,tk.BOTTOM)
       return aFrame


   def speedFrame(self,mFrame):
       aFrame = self.subFrame(mFrame,'speed')
       sFont = tkFont.Font(root=mFrame,family="Courier",size=72)
       self.speedvar = tk.StringVar()
       speedLabel = tk.Label(aFrame,anchor=tk.W,textvariable=self.speedvar,font=sFont)
       self.speedvar.set("{:2.1f}".format(self.speedValue))
       speedLabel.pack(side=tk.LEFT)
       kmhLabel = tk.Label(aFrame,text="km/h",justify=tk.LEFT)
       kmhLabel.pack(side= tk.LEFT)

   def addDistance(self, value):
       self.setOdometer(self.odometerValue + value)


   def setOdometer(self, value):
       self.odometerValue =value
       self.odometerVar.set("{:.1f}".format(value))

   def setTimer(self, value):
       self.TimerValue =value
       hour= int(value / 3600)
       min = int((value - (hour * 3600)) / 60)
       sec = (value - (hour * 3600) - (min * 60))
       self.TimerVar.set("{:02}:{:02}:{:04.1f}".format(hour,min,sec))

   def setAvgSpeed(self, value):
       self.avgSpeedValue =value
       self.avgSpeedVar.set("{:.1f}".format(value))



   def timerFrame(self,mFrame):
       aFrame = self.subFrame(mFrame,'Timer')
       self.TimerValue = 0
       self.TimerVar = tk.StringVar()
       sFont = tkFont.Font(root=mFrame,family="Courier",size=32)
       TmLabel = tk.Label(aFrame,textvariable=self.TimerVar,font=sFont)
       TmLabel.pack(side= tk.BOTTOM)
       self.setTimer(0)

   def avgSpeedFrame(self,mFrame):
       aFrame = self.subFrame(mFrame,'Average speed')
       self.avgSpeedValue = 0.0
       self.avgSpeedVar = tk.StringVar()
       sFont = tkFont.Font(root=mFrame,family="Courier",size=24)
       tk.Label(aFrame,text="km/h").pack(side=tk.RIGHT)
       avgLabel = tk.Label(aFrame,textvariable=self.avgSpeedVar,font=sFont)
       avgLabel.pack(side= tk.RIGHT)
       self.setAvgSpeed(0)


   def odometerFrame(self,mFrame):
       aFrame = self.subFrame(mFrame,'Odometer')
       self.odometerValue = 0.0
       self.odometerVar = tk.StringVar()
       sFont = tkFont.Font(root=mFrame,family="Courier",size=24)
       tk.Label(aFrame,text="km   ").pack(side=tk.RIGHT)
       odometerLabel = tk.Label(aFrame,textvariable=self.odometerVar,font=sFont)
       odometerLabel.pack(side= tk.RIGHT)
       self.setOdometer(0)

   def settingsFrame(self,mFrame):
       aFrame = self.subFrame(mFrame,'Resistance settings')
       bFrame = tk.Frame(aFrame)
       bFrame.pack(side=tk.TOP)
       self.settings = tk.IntVar()
       for i in range(8):
         tk.Radiobutton(bFrame,text = "{}".format(i),variable=self.settings,value=i).grid(row = i/4,column= i % 4)

   def ResetAll(self):
       self.odometerValue=0;
       self.startTime=time.time()
       self.setTimer(0)
       self.setAvgSpeed(0)

   def setZeroSpeed(self):
       self.dynamicMovingAverage= [0] * (dynamicMovingAverageMaxCount +1)
       self.dynamicMovingAverageCount=0


   def resetFrame(self,mFrame):
       tFrame = tk.Frame(mFrame)
       tFrame.pack(side = tk.BOTTOM,fill=tk.X)
       sFont = tkFont.Font(root=mFrame,family="Courier",size=24)
       b = tk.Button(tFrame, text ="Reset", command= self.ResetAll,font=sFont)
       b.pack()


   def separator(self,master,s_side=tk.BOTTOM):
       Fr = tk.Frame(master,height=2,bg="black")
       Fr.pack(side=s_side,fill=tk.X)

   def update_clock(self):
       self.deci = self.deci + 1
       self.ctime = time.time()
       self.setTimer(self.ctime - self.startTime)

       if self.deci > 9:
        self.deci=0
        if self.dynamicMovingAverageCount > 2:
          self.setAvgSpeed(self.odometerValue / (self.TimerValue / 3600.0))

       if self.sensorTimer >0:
         self.sensorTimer =self.sensorTimer - 1
         if self.speedValue > 99.9 :
          self.speedValue=0.0
       else:
#         self.setZeroSpeed()
         self.speedValue=0.0

       self.speedvar.set("{:4.1f}".format(self.speedValue))
       self.root.after(100,self.update_clock)


   def gotPulse(self):
       self.sensorTimer=20
       ctime= time.time()
       self.dynamicMovingAverage[dynamicMovingAverageMaxCount]=ctime
       deltaTime = ctime - self.dynamicMovingAverage[dynamicMovingAverageMaxCount - self.dynamicMovingAverageCount]
       for i in range(dynamicMovingAverageMaxCount):
         self.dynamicMovingAverage[i]=self.dynamicMovingAverage[i+1]
       if deltaTime == 0.0:
         speed=0.0
       else:
         speed = self.dynamicMovingAverageCount * WheelCircumference / deltaTime
       self.dynamicMovingAverageCount = self.dynamicMovingAverageCount+1
       if self.dynamicMovingAverageCount > dynamicMovingAverageMaxCount:
         self.dynamicMovingAverageCount = dynamicMovingAverageMaxCount
       #convert to kmh
       speed = speed * 3600.0 / 1000.0
       self.speedValue = speed
       self.addDistance(WheelCircumference / 1000.0)



GPIO.setmode(GPIO.BCM)
GPIO.setup(WheelSensorGPIO, GPIO.IN,pull_up_down = GPIO.PUD_UP)


app=App()

def gotWheelTurn(channel):
       app.gotPulse()

GPIO.add_event_detect(WheelSensorGPIO, GPIO.FALLING,callback = gotWheelTurn,bouncetime=100)


app.mainloop()