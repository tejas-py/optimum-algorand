from algosdk import encoding, atomic_transaction_composer, transaction
import API
from contract.application import Optimum
from beaker import client

# Connect to Algod-Client in Testnet Network
algod_client = API.connection.algo_conn("testnet")
indexer_client = API.connection.connect_indexer("testnet")
# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = atomic_transaction_composer.AccountTransactionSigner("a" * 32)


# Optimum App optin by the wallet
def app_opt_in(sender_wallet, app_id):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # set the params for the transactions
    params = algod_client.suggested_params()
    params.fee = 1000
    params.flat_fee = True

    atc = atomic_transaction_composer.AtomicTransactionComposer()
    app_client.add_transaction(
        atc=atc,
        txn=transaction.AssetOptInTxn(
            sender_wallet,
            params,
            app_id
        )
    )

    # extract the transaction from the ATC
    txn_details = atc.txn_list[0].txn
    result = [{'txn': encoding.msgpack_encode(txn_details)}]

    return result


# Optimum ASA optin by the wallet
def asset_opt_in(sender_wallet, asset_id):

    # transaction params
    params_optin = algod_client.suggested_params()

    # Optin to OPT ASA by fee account
    atc = atomic_transaction_composer.AtomicTransactionComposer()
    atc.add_transaction(
        atomic_transaction_composer.TransactionWithSigner(
            txn=transaction.AssetTransferTxn(
                sender_wallet,
                params_optin,
                sender_wallet,
                0,
                asset_id
            ),
            signer=ACCOUNT_SIGNER
        )
    )

    # extract the transaction from the ATC
    txn_details = atc.txn_list[0].txn
    result = [{'txn': encoding.msgpack_encode(txn_details)}]

    return result
