# Corpus normativo (input per i criteri core C1–C9)

Questa cartella contiene il **corpus normativo chiuso** su cui gli agenti si ancorano, tramite RAG, per valutare i criteri core **C1–C9**.

## I documenti non sono nel repository

Il prototipo è **agnostico rispetto ai documenti interni** usati: i documenti del corpus **non** sono versionati in git, così lo strumento resta generale e riutilizzabile con corpora diversi.

Per usarlo, inserisci qui i tuoi documenti normativi in formato **Markdown** (`.md`), uno per documento, poi costruisci l'indice vettoriale:

```bash
cd backend
uv run python scripts/ingest_corpus.py
# (sul branch Docker: docker compose --profile seed run --rm seed)
```

## Tagging

La mappatura dei chunk ai criteri/agenti è configurata in [`../tagging_rules.yaml`](../tagging_rules.yaml), tarata sul corpus sperimentale. Se usi documenti diversi, adatta quelle regole di conseguenza.

## Corpus sperimentale

**Contattami** se vuoi i documenti che ho usato per valutare i criteri core negli esperimenti, così da inserirli qui.
