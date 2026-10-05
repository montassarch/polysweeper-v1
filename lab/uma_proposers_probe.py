"""Probe: who proposes Polymarket results on-chain (public Polygon RPC, read-only)."""
import json, urllib.request, collections, sys, time
R = "https://polygon-bor-rpc.publicnode.com"
def rpc(m, p):
    r = urllib.request.Request(R, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(),
                               headers={"Content-Type": "application/json", "User-Agent": "curl/8.0"})
    return json.load(urllib.request.urlopen(r, timeout=60))
bn = int(rpc("eth_blockNumber", [])["result"], 16)
adapters = sys.argv[1:] or ["65070BE91477460D8A7AeEb94ef92fe056C2f2A7"]
L = []
for a in adapters:
    req = "0x" + "0" * 24 + a.lower()
    for k in range(int(sys.argv[0] and 6)):
        lo = bn - (k + 1) * 900; hi = bn - k * 900
        out = rpc("eth_getLogs", [{"fromBlock": hex(lo), "toBlock": hex(hi), "topics": [None, req]}])
        if "error" in out: print(out["error"]); break
        L += out["result"]; time.sleep(0.5)
print("logs", len(L), "blocks", 6 * 900)
c = collections.Counter((l["address"], l["topics"][0][:14], len(l["topics"])) for l in L)
for k, v in c.most_common(8): print(k, v)
# proposer = topic[2] for events with 3 topics
prop = collections.Counter(l["topics"][2][-40:] for l in L if len(l["topics"]) >= 3)
print("distinct topic2 addresses", len(prop), prop.most_common(10))
