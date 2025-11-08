# Decode shredstreams (client Python)

Questo repository ora contiene esclusivamente il client Python asincrono per
collegarsi allo Shredstream Proxy di Jito, filtrare le transazioni e stamparle
con un timestamp con precisione al millisecondo. Tutti i file del precedente
esempio in Rust sono stati rimossi perché non più necessari.

## Installazione rapida

```bash
git clone https://github.com/Shyft-to/shredstream-decode-examples.git
cd shredstream-decode-examples
python -m venv .venv
source .venv/bin/activate  # su Windows: .venv\Scripts\activate
pip install -r requirements-python.txt
```

## Client Python

Il client principale si trova in `shredstream_client.py` e usa gRPC per
streammare gli slot dalla proxy. Puoi filtrare le transazioni per account e
continuare a decodificarle anche se il pacchetto `solders` installato non
include le binding native del ledger: in quel caso verrà usato il decoder
Python integrato.

### 1. Genera le stubs protobuf

Le definizioni `.proto` necessarie sono già incluse nella cartella
`jito_protos/protos/`. Per rigenerare i moduli Python esegui:

```bash
python -m python.generate_protos
```

Lo script configura automaticamente gli include di `grpcio-tools` e produce i
file `shredstream_pb2.py` e `shredstream_pb2_grpc.py` in
`python/jito_protos/shredstream/`.

### 2. Avvia il client

```bash
python -m shredstream_client --shredstream-uri <url> --x-token <authtoken>
```

Su Windows puoi usare il launcher `py`:

```powershell
py -m shredstream_client --shredstream-uri <url> --x-token <authtoken>
```

Opzioni utili:

- `--account-include` → elenco di chiavi pubbliche (separate da spazi) per
  filtrare le transazioni di interesse.
- `--keepalive-seconds` → intervallo del ping gRPC (default 15 secondi).
- `--max-retries` → numero massimo di tentativi di riconnessione prima di
  abortire.

### 3. Note aggiuntive

- `--shredstream-uri` accetta sia formati `host:porta` sia URL completi con
  schema `http://` o `https://`. Nel caso di HTTPS viene aperto automaticamente
  un canale TLS.
- Ogni chiave pubblica Solana in base58 rappresenta 32 byte e misura circa
  43-44 caratteri: assicurati di incollare l'intera stringa senza spazi extra.
- Se il pacchetto `solders` installato non fornisce il tipo `Entries`, il
  client ripiega su un decoder pure-Python. Per prestazioni ottimali installa
  invece il wheel con le binding native: `pip install "solders[ledger]>=0.27"`.

## Risorse utili

- Documentazione Shredstream Proxy:
  <https://github.com/jito-labs/shredstream-proxy>
- Protobuf ufficiali Jito (se vuoi aggiornarli manualmente):
  <https://github.com/jito-labs/mev-protos>
