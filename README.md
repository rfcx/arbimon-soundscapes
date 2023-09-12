# Soundscapes

### Integration with Arbimon

Start up an Arbimon db

```bash
make serve-up
```

Then run a soundscape

```bash
make serve-run SCRIPT=batch_legacy
```

(This runs `soundscapes/batch_legacy.py`.)

When you have finished

```bash
make serve-down
```
