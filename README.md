# Thereminuscule Signal Library

> Go to [this page(https://wildflux-experience.github.io/thereminuscule-signal-library/)] to navigate in the library !

A library of signal to be played with the [Thereminuscule](https://github.com/wildflux-experience/thereminuscule-engine)'s Dataplayer component. Data comes from real world measurements.

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
   |- assets/ <- A folder to store additional files such as the output of the plot.py script
```
To add new category, simply create new folder.

To add new signal, copy-paste folder `category-template/signal-template/` into the desired category and start editing the source.


