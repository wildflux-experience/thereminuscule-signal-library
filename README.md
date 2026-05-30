# Thereminuscule's Signal Library

A library of signal to be played with the `Dataplayer` component. Data comes from real world measurements.

These signals typically are time-serie or ordered records that relates to physical variables or events.

Signals are sorted by categories : 

```
thereminuscule-signal-library/category-name/signal-name/
```

Signals are stored like this:

```
signal-name/
   |- README.md <- A quick description of the data
   |- process.py <- The script that process and format raw data and generate the signal.csv file
   |- plot.py <- A script to show data. Output are stored in assets/
   |- signal.csv <- The signal to be played with the Thereminuscule
   |- config_dataplayer.json <- The corresponding config info for the Dataplayer to be copied into the Thereminuscule config file
   |- raw/ <- Raw data before processing and formating
   |- assets/ <- A folder to store additional files such as the output of the plot.py script
```


