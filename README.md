# Soundscapes

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
