# Anchor completi, evidenze selezionate e contesto fisso

Prove del **16–17 settembre 2026**; resoconto completato il **28 settembre 2026**.
MacBook Air M2, 8 GB. **Costi API: 0 USD.**

## Decisione

Si adottano la correzione che consegna gli anchor completi ai prompt e
l'esclusione del README dall'inventario normativo. Si conserva un percorso
sperimentale riproducibile per selezionare evidenze originali e confrontare
riferimenti fissi. **Qwen e le soglie candidate non vengono attivati come nuova
configurazione di valutazione nell'applicazione.**

Le citazioni ricostruite sono fedeli per costruzione, ma i risultati mostrano
ancora errori di interpretazione. Il contesto fisso riduce il testo duplicato;
non abbiamo ancora una dimostrazione di accuratezza o velocità generalizzabile.

## Correzioni applicate

La pipeline passava specifiche non vuote contenenti soltanto descrizioni:
i builder le preferivano al proprio catalogo completo, perdendo gli anchor.
Ora [core_rubric.py](../../backend/app/evaluation/agents/prompts/core_rubric.py)
fornisce un catalogo comune, completa gli input parziali e rifiuta codici,
responsabilità o anchor esplicitamente incompleti. Gli anchor esistenti sono
stati trasferiti senza riscriverne il testo, verificato rispetto alla versione
precedente. Un test cattura il prompt effettivamente consegnato al client.

Le versioni sono **A1 v8, A2 v2, A3 v2, A4 v11**, condivise fra agenti e
metadati. Il frontend distingue questo profilo dalla configurazione storica
usata nella tesi: la validazione precedente non si trasferisce automaticamente.

Il README del corpus era contato come documento normativo. Inventario e
importazione ora usano la stessa selezione di sorgenti, escludendo README.md
anche con maiuscole diverse e conservando gli altri documenti, compresi quelli
privi di tag. Questo risolve i tre fallimenti preesistenti nei test del corpus.
Nessun indice persistente è stato ricostruito e non sono stati chiamati embedding
remoti: un indice già popolato non viene ripulito retroattivamente dal solo fix.

## Disegno delle prove

Un solo syllabus, **Internet of Things**, già usato nello sviluppo; una richiesta
per agente/configurazione. Non è un campione indipendente di validazione.

Tutte le prove usano Qwen3.5:4b **Q4_K_M**, Ollama **0.32.15**, contesto 16.384,
output massimo 2.048 token, temperatura 0,1, seed 42, thinking disabilitato e
una richiesta alla volta. Il server è locale, con cloud disabilitato; niente
Gemini, Vertex, embedding remoti, download automatici o ripieghi a pagamento.
Il digest del modello e gli hash degli input e del codice sono nel
[registro riassuntivo](anchors-evidence-2026-09-17.json).

La politica `current_v1` applica i builder correnti al syllabus e al contesto
normativo delle fixture storiche. Non ripete estrazione, selezione dei campi o
retrieval dell'applicazione. Le versioni differiscono da quelle di Gemini
archiviate: **l'accordo con Gemini non misura l'accuratezza umana né l'effetto
isolato degli anchor**. Il controllo `current_without_anchors_v1` è implementato
e verificato sui 20 casi, ma non è stato eseguito con inferenza reale.

| Prova | Agenti | Evidenze | Contesto | Risposte valide secondo il protocollo |
|---|---|---|---|---:|
| A, 16 settembre | A1–A4 | Citazioni generate (`literal`) | Archiviato | 4/4 |
| B, 17 settembre | A1–A4 | ID, versione 1 | Archiviato | 4/4 |
| C, 17 settembre | Solo A1 | ID, versione 2 | Archiviato | 1/1 |
| D, 17 settembre | Solo A2 | ID, versione 1 | Fisso deduplicato | 1/1 |

Sono **10 tentativi**, tutti salvati, senza correzioni nascoste della risposta.
La prova D conserva deliberatamente il protocollo di B: cambia soltanto il
contesto rispetto a B/A2. Non equivale all'approvazione della versione 1.

## Punteggi e divergenze

Un trattino significa prova non eseguita, non punteggio mancante da imputare.

| Criterio | Gemini storico | A: citazioni generate | B: ID v1 | C: ID v2, A1 | D: contesto fisso, A2 |
|---|---:|---:|---:|---:|---:|
| C1 | 2 | 2 | **0** | 2 | — |
| C2 | 0 | 0 | 0 | 0 | — |
| C3 | 1 | 1 | 1 | — | 1 |
| C4 | 2 | 1 | 1 | — | 2 |
| C5 | 1 | 1 | 0 | 1 | — |
| C6 | 2 | 2 | 2 | — | — |
| C7 | 2 | 1 | 2 | — | — |
| C8 | 2 | 2 | 2 | — | — |
| C9 | 1 | 2 | 2 | — | — |

L'accordo descrittivo è 6/9 in A, 5/9 in B, 3/3 in C e 2/2 in D.
Non si devono combinare le colonne parziali per presentare una configurazione
completa mai eseguita.

- **C1, prova B: errore grave.** Qwen dichiara presenti solo le informazioni di
  programmazione, nonostante le altre sezioni italiane siano nel prompt. Usa
  campi inglesi vuoti per sostenere l'assenza delle sezioni italiane. La risposta
  supera il vecchio protocollo perché gli ID e le assenze esistono davvero.
- **C1, prova C: il caso viene corretto.** La versione 2 conserva i campi testuali
  come stringhe con marcatori, invece di trasformarli in oggetti, e limita i
  campi selezionabili per criterio. C1 torna a 2 e C2 documenta tre assenze
  inglesi verificate. Una citazione di C1 per la programmazione contiene solo
  il numero «1»: anche una provenienza valida può fornire un supporto debole.
- **C5: regola e motivazione ancora incoerenti.** In A e C il modello assegna 1
  pur descrivendo un elenco di soli nomi di corsi senza conoscenze richieste,
  condizione esplicita dell'anchor attivo 0. In B assegna 0. Qui tornare allo
  stesso punteggio di Gemini non dimostra un miglioramento. La proposta candidata
  tratta diversamente questo confine, ma quella proposta non era attiva.
- **C3/C4:** il modello cambia interpretazione fra genericità e specificità.
  Nel confronto B→D, con gli stessi passaggi normativi unici e le stesse evidenze
  selezionate, C4 passa da 1 a 2. Serve una lettura umana indipendente per
  stabilire quale interpretazione sia fondata.
- **C7, prova A:** la motivazione richiede dettaglio settimanale e riferimenti
  specifici per modulo, requisiti non universalmente necessari nell'anchor.
- **C9:** entrambe le prove complete assegnano 2 e menzionano la versione
  inglese assente nonostante il perimetro del criterio. In A mancano citazioni;
  in B due frammenti leggibili non dimostrano un'ispezione esaustiva. Le affermazioni
  del modello sull'accessibilità dei collegamenti non sono verifiche di rete.

## Evidenze: miglioramento tecnico e limite semantico

| Prova | Citazioni letterali verificate | Giudizi senza citazioni |
|---|---:|---:|
| A | 15/28 | 1: C9, senza supporto testuale |
| B | 38/38 | 0 |
| C | 10/10 | 1: C2, con tre assenze verificate |
| D | 9/9 | 0 |

Le percentuali non misurano la stessa capacità: in A il modello copia testo;
in B/C/D seleziona ID e il programma ricostruisce sottostringhe originali.
Le assenze sono una forma di supporto distinta e non sono conteggiate come
citazioni vuote o inventate.

La versione 2 rifiuta ID sconosciuti o duplicati, assenze false e campi estranei
al criterio. Per esempio C1 usa sezioni italiane; C2 usa i gruppi informativi
inglesi; C5 usa i prerequisiti. Il contratto strutturato e il controllo della
risposta applicano gli stessi confini. Non verificano automaticamente la
pertinenza di ogni frase, la motivazione libera o il punteggio.

La verifica senza inferenza delle risposte B con i confini v2 rifiuta A1 e
accetta A2/A3/A4. È un controllo dei campi, non un nuovo risultato generativo.
La generazione v2 è stata provata soltanto su A1; gli altri agenti hanno test
di integrità dei dati e del contratto, non una validazione con il modello.
La versione 1 rimane disponibile per riprodurre il fallimento osservato.

## Contesto fisso: cosa è dimostrato

Per tutti e cinque i casi archiviati di **A2 e A4**, i test verificano le stesse
associazioni criterio–passaggio–testo. Il pacchetto fisso seleziona questi testi
da una fixture controllata tramite hash e conserva i riferimenti e le
associazioni a tutti i criteri. Non ripubblica una copia separata delle fonti.

In A2 le sei voci diventano quattro passaggi unici: **9.732 → 6.150 caratteri
di testo normativo**. In A4 restano due passaggi. A1/A3 sono rifiutati prima
dell'inferenza: non esiste una selezione fissa validata per loro.

Il confronto reale A2 mantiene modello, rubrica, dati e protocollo v1:

| Misura | B/A2: contesto archiviato | D/A2: contesto fisso |
|---|---:|---:|
| Caratteri dell'intero prompt | 28.218 | 20.724 |
| Token del prompt riportati dal runtime | 7.789 | 5.541 |
| Token generati | 399 | 451 |
| Tempo totale osservato | 228,313 s | 63,678 s |
| C3 / C4 | 1 / 1 | 1 / 2 |
| Citazioni verificate | 9/9 | 9/9 |

La riduzione del testo è verificabile. **Il calo del tempo non è una stima
controllata dell'accelerazione:** cache, carico della macchina, swap e condizioni
termiche non erano isolati, e manca una serie di ripetizioni alternate.
Entrambe le prove riusano già contesti congelati senza RAG: non misurano il
risparmio del retrieval della pipeline completa. Per A4 manca una prova reale
con contesto fisso.

Il pacchetto è storico, non un profilo di conformità UniCT 26.04. Anche i nomi
di versione dei documenti sono metadati archiviati: per esempio l'etichetta
SUA «2026» non certifica una nuova edizione della fonte del 2018. La copertura
nei cinque casi non prova che il pacchetto sia sufficiente per ogni syllabus.

## Verifiche e adozione successiva

Suite backend del 17 settembre: **1.273 test superati, nessun fallimento**;
build frontend e Ruff sui file Python modificati superati. Il 28 settembre
le impronte del codice coincidono con l'ultima prova: sono stati completati
il resoconto e il registro, senza nuovi cambiamenti all'inferenza.

I test coprono la consegna effettiva degli anchor, la conservazione del testo
e dei tipi di campo sui 20 casi, gli offset delle citazioni, gli errori del
contratto, l'isolamento dalle configurazioni cloud e l'integrità del pacchetto.
Non sostituiscono la validazione semantica.

La prossima decisione riguarda condizioni ed esempi di confine della
[rubrica candidata](RUBRIC_PROPOSAL_V2.md), con giudizi umani su casi nuovi.
Finché questo manca, i risultati giustificano migliori controlli e tracciabilità,
non l'affermazione che Qwen equivalga a Gemini o che le nuove soglie siano ottimali.

Prompt, risposte e cataloghi integrali rimangono negli artefatti locali ignorati
da Git. Il registro pubblicato conserva tutti i tentativi, configurazioni,
punteggi e hash. Il commit indicato nei manifest era il HEAD durante lo sviluppo;
le impronte dei file identificano il codice effettivamente eseguito.
