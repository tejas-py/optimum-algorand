from algosdk import encoding, atomic_transaction_composer, transaction, logic
from connection import algo_conn
from application import Optimum
from beaker import client
import utils

# Connect to Algod-Client and Indexer-Client in Testnet Network
algod_client = algo_conn("testnet")
# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = atomic_transaction_composer.AccountTransactionSigner("a" * 32)

