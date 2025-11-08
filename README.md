# Decode shredstreams

```bash
git clone https://github.com/Shyft-to/shredstream-decode-examples.git

cargo run -- --shredstream-uri <url> --x-token <authtoken>
```

- `x-token` _optional_
- `--account-include` (optional) → Space-separated list of accounts to filter transactions by. If omitted, all transactions will be printed.


![screenshot-1](assets/usage-screenshot-1.png?raw=true "Screenshot")
## View Count
If you only want to see counts of slots, entries, and transactions, remove the comments from this section in [main.rs](src/main.rs "main.rs"):
```rust
                // println!(
                //     "slot {}, entries: {}, transactions: {}",
                //     slot_entry.slot,
                //     entries.len(),
                //     entries.iter().map(|e| e.transactions.len()).sum::<usize>()
                // );
```

## View Transactions
- By default, all transactions will be streamed and printed.

- To restrict output to transactions involving specific accounts, pass `--account-include`.
### Example
```bash
cargo run -- --shredstream-uri <url> --x-token <authtoken> --account-include 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4
```

### Preview:
![screenshot-2](assets/usage-screenshot-2.png?raw=true "Stream transactions from shredstream")

## Notes

Jito Shredstream Proxy: [https://github.com/jito-labs/shredstream-proxy]

## Python client

A Python port of the streaming client is available in `shredstream_client.py`.

### 1. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-python.txt
```

> [!NOTE]
> Il client scandaglia automaticamente i moduli del pacchetto `solders`
> (inclusi quelli dichiarati nei metadati del wheel) alla ricerca del tipo
> `Entries`, provando percorsi come `solders.entry`, `solders.ledger.entry` e
> qualsiasi modulo che contenga "entry" o "ledger" nel nome. Se nessuno dei
> moduli installati espone `Entries`, il client ripiega su un decoder puro
> Python integrato che ricostruisce le transazioni leggendo direttamente il
> formato binario degli `Entry`. Per prestazioni ottimali continua comunque a
> essere consigliata l'installazione del wheel con le binding native del
> ledger, ad esempio `pip install "solders[ledger]>=0.27"`.

### 2. Fetch the protobuf definitions

The necessary `.proto` files live under `jito_protos/protos/` and are now part of
this repository, so no extra submodule checkout is required. If you prefer to
pull the latest versions from [`mev-protos`](https://github.com/jito-labs/mev-protos),
you can still replace the files manually, but the committed copies are enough to
generate the Python bindings out of the box.

### 3. Generate the protobuf stubs

The Python client expects the generated protobuf code under `python/jito_protos/shredstream/`.
Once the `.proto` definitions are present in `jito_protos/protos/` (they ship with
this repo), run one of the following commands to generate the Python bindings
in-place. The helper configures the include paths bundled with `grpcio-tools` so
that `google/protobuf/*.proto` is found correctly:

```bash
# macOS / Linux (single line)
python -m grpc_tools.protoc -I jito_protos/protos --python_out=python --grpc_python_out=python jito_protos/protos/shared.proto jito_protos/protos/shredstream.proto

# Windows PowerShell (single line)
python -m grpc_tools.protoc -I jito_protos/protos --python_out=python --grpc_python_out=python jito_protos\protos\shared.proto jito_protos\protos\shredstream.proto

# Windows cmd.exe (use caret for line continuations)
python -m grpc_tools.protoc ^
  -I jito_protos/protos ^
  --python_out=python ^
  --grpc_python_out=python ^
  jito_protos/protos/shared.proto \
  jito_protos/protos/shredstream.proto

# Cross-platform helper (runs the command via a Python module)
python -m python.generate_protos
```

This writes `shredstream_pb2.py` and `shredstream_pb2_grpc.py` into the
`python/jito_protos/shredstream/` package. The client automatically adds the `python/`
directory to `PYTHONPATH`, and if the generated modules are missing it will invoke the
helper above for you. No additional packaging steps are required.

### 4. Run the client

```bash
python shredstream_client.py --shredstream-uri <url> --x-token <authtoken>
```

On Windows you can use the `py` launcher with either the script path or the
module flag:

```powershell
py shredstream_client.py --shredstream-uri <url> --x-token <authtoken>
# or
py -m shredstream_client --shredstream-uri <url> --x-token <authtoken>
```

You can also pass `--account-include` with a space-separated list of accounts to filter by.

> [!NOTE]
> Il parametro `--shredstream-uri` accetta sia `host:porta` sia URL completi con schema.
> Se passi un endpoint `https://example.com` il client userà automaticamente TLS (porta
> predefinita 443 se non specificata); con `http://` oppure senza schema userà invece una
> connessione non cifrata.

> [!TIP]
> Ogni chiave pubblica Solana in base58 rappresenta 32 byte e misura circa 43-44 caratteri.
> Se il client segnala "Invalid pubkey provided", controlla di aver incollato l'intera
> stringa (senza andare a capo) e che non ci siano spazi aggiuntivi prima o dopo.
