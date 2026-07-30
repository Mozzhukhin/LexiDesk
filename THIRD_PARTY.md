# Third-party data and software

LexiDesk does not bundle language data in its source repository. Its setup
scripts download the following resources into the user's local data directory.

## FreeDict / WikDict EN↔RU dictionaries

- Project: [FreeDict](https://freedict.org/)
- Source data: [English–Russian](https://download.freedict.org/generated/eng-rus/)
  and [Russian–English](https://download.freedict.org/generated/rus-eng/)
- Data origin: WikDict, Wiktionary, and DBnary
- License: Creative Commons Attribution-ShareAlike 3.0 Unported

LexiDesk transforms the TEI files into a local SQLite search index. The
transformed database remains under the same CC BY-SA 3.0 terms. The original
TEI files are removed after indexing to avoid duplicate disk usage.

## Argos Translate

- Project: [Argos Translate](https://github.com/argosopentech/argos-translate)
- Purpose: offline neural translation fallback for words or phrases not found
  in the bilingual dictionary
- Software license: MIT / CC0; individual model metadata is retained inside
  each installed model package

## Princeton WordNet

- Project: [Princeton WordNet](https://wordnet.princeton.edu/)
- Distribution: [NLTK Data](https://www.nltk.org/howto/wordnet.html)
- Purpose: sense-specific English example sentences and definitions
- License: Princeton WordNet License

LexiDesk converts WordNet records into a compact local SQLite index. Runtime
lookups are offline and do not import or scan the full corpus.

LexiDesk itself is licensed under MIT. Third-party data keeps its original
license and attribution requirements.
