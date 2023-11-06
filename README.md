# Soundscapes

### Definition

We define a Soundscape as a time/frequency surface plot of a given feature in a set of recordings. Our soundscapes plot the number of recording of a specific time having a peak in a specific frequency region above a threshold amplitude in their computed mean spectrum. We express the amplitudes as a real number from 0 to 1, and can be taken as either relative to the maximum amplitude value within all recordings used in the soundscape, or a an absolute value where 1 is the highest amplitude that can be represented in each recording.

For computing the mean spectrum of a recording and its peaks we use the meanspec and fpeaks functions from the seewave R package. To compare with absolute amplitude thresholds we normalize the recording samples so that 1 is the highest represented value in the audio channel. To compare with relative to maximum amplitude thresholds we compute the maximum amplitude within the set of recordings and scale the threshold so that 1 represents this maximum value.

### Basic mode

_TODO_ - Input folder of audio files. Output soundscape results as files

### Arbimon mode

Input Arbimon project, site list and parameters. Output Arbimon job status (while running) and soundscape results to Arbimon DB and storage on completion.

#### Locally

Download mock S3 data as described in [Store](./store/README.md). Core mock data is sufficient.

Copy `example.env` to `.env` and define your soundscape parameters. (Project 1907 is a default that is defined in the mock db and store, it has recordings in 2020 and 2022.)

Start up an Arbimon mock DB and Store, seed it.

```bash
make serve-up
```

Run the soundscape batch job (`soundscapes/batch_legacy.py`).

```bash
make serve-run SCRIPT=batch_legacy
```

Inspect the results in mock store.

```bash
make serve-run SCRIPT=s3_get project_1907
```

When you have finished

```bash
make serve-down
```
