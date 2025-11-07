# Decode shredstreams

```bash
git clone https://github.com/Shyft-to/shredstream-decode-examples.git --recurse-submodules

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

### 2. Generate the protobuf stubs

The Python client expects the generated protobuf code under `python/jito_protos/shredstream/`.
The repo already contains the `.proto` definitions under `jito_protos/protos/`; run the
following command to generate the Python bindings in-place:

```bash
python -m grpc_tools.protoc \
  -I jito_protos/protos \
  --python_out=python \
  --grpc_python_out=python \
  jito_protos/protos/shredstream/shredstream_proxy.proto
```

This writes `shredstream_proxy_pb2.py` and `shredstream_proxy_pb2_grpc.py` into the
`python/jito_protos/shredstream/` package. The client automatically adds the `python/`
directory to `PYTHONPATH`, so no additional packaging steps are required.

### 3. Run the client

```bash
python shredstream_client.py --shredstream-uri <url> --x-token <authtoken>
```

You can also pass `--account-include` with a space-separated list of accounts to filter by.
