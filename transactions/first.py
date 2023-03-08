from algosdk.atomic_transaction_composer import AtomicTransactionComposer, TransactionWithSigner
from algosdk import transaction
import connection
import application

algod_client = connection.algo_conn("testnet")


def main(app_id, wallet_address):

    atc_sp = algod_client.suggested_params()
    atc = AtomicTransactionComposer()
    atc.add_transaction(

    )

