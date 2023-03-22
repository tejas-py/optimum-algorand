from algosdk.v2client import algod, indexer


# Connection to the algorand network
def algo_conn(network):
    if network == 'sandbox':
        algod_address = "http://localhost:4001"
        algod_token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        headers = {"X-API-Key": algod_token}
        conn = algod.AlgodClient(algod_token, algod_address, headers)
        return conn

    if network == 'testnet':
        algod_address = "https://testnet-algorand.api.purestake.io/ps2"
        algod_token = "ksZOvoviIZ163QVUoTht86g0qMBmLJIS9hcFpcNl"
        headers = {"X-API-Key": algod_token}
        conn = algod.AlgodClient(algod_token, algod_address, headers)
        return conn

    if network == 'mainnet':
        algod_address = "https://mainnet-algorand.api.purestake.io/ps2"
        algod_token = "ksZOvoviIZ163QVUoTht86g0qMBmLJIS9hcFpcNl"
        headers = {"X-API-Key": algod_token}
        conn = algod.AlgodClient(algod_token, algod_address, headers)

        return conn.algod_address


# Connection to Algorand Indexer
def connect_indexer(network):
    if network == 'sandbox':
        algod_indexer = "http://localhost:8980"
        indexer_token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        headers = {"X-API-Key": indexer_token}
        myindexer = indexer.IndexerClient(indexer_token, algod_indexer, headers)
        return myindexer

    if network == 'testnet':
        algod_indexer = "https://testnet-algorand.api.purestake.io/idx2"
        indexer_token = "ksZOvoviIZ163QVUoTht86g0qMBmLJIS9hcFpcNl"
        headers = {"X-API-Key": indexer_token}
        myindexer = indexer.IndexerClient(indexer_token, algod_indexer, headers)
        return myindexer

    if network == 'mainnet':
        algod_indexer = "https://mainnet-algorand.api.purestake.io/idx2"
        indexer_token = "ksZOvoviIZ163QVUoTht86g0qMBmLJIS9hcFpcNl"
        headers = {"X-API-Key": indexer_token}
        myindexer = indexer.IndexerClient(indexer_token, algod_indexer, headers)
        return myindexer
