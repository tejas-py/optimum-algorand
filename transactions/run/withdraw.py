from algosdk import encoding, atomic_transaction_composer, transaction, logic
import connection
from application import Optimum
from beaker import client
import utils


# Connect to Algod-Client and Indexer-Client in Testnet Network
algod_client = connection.algo_conn("testnet")
indexer_client = connection.connect_indexer('testnet')
# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = atomic_transaction_composer.AccountTransactionSigner("a" * 32)

TEN_BILLION = 10000000000000000


def withdraw(sender_wallet, fee_address, app_id, asset_id, opt_amt):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # create Atomic Transaction Composer to build transaction group
    atc = atomic_transaction_composer.AtomicTransactionComposer()

    # Create Param for transaction 1
    params_txn1 = algod_client.suggested_params()

    # create 1st transaction object
    app_client.add_transaction(
        atc=atc,
        txn=transaction.AssetTransferTxn(
            sender_wallet,
            params_txn1,
            logic.get_application_address(app_id),
            opt_amt,
            asset_id
        )
    )

    # create param for transaction 2
    params_txn2 = algod_client.suggested_params()
    params_txn2.fee = 3000

    # create 2nd transaction object
    app_client.add_method_call(
        atc=atc,
        method=Optimum.exchange,
        sender=sender_wallet,
        foreign_assets=[asset_id],
        accounts=[fee_address],
        suggested_params=params_txn2
    )

    # fetch the transaction objects
    txn_1 = atc.txn_list[0]
    txn_2 = atc.txn_list[1]

    # Group Transactions
    print("Grouping transactions...")
    group_id = transaction.calculate_group_id([txn_1, txn_2])
    print("...computed groupId: ", group_id)
    txn_1.group = group_id
    txn_2.group = group_id

    txn_grp = [{'txn': encoding.msgpack_encode(txn_1)},
               {'txn': encoding.msgpack_encode(txn_2)}]

    return txn_grp


# Computes ALGO amount to withdraw from the custodial wallets, depending on the OPT we
# will submit, using the current exchange rate.
def compute_algo_withdraw_amt_from_opt(app_id, asset_id, opt_amt):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # get the application address
    app_wallet_address = logic.get_application_address(app_id)

    # get the OPT holding of the app
    res = indexer_client.lookup_account_assets(address=app_wallet_address, asset_id=asset_id)
    opt_holding_of_app = res['assets'][0]['amount']

    # get the application account information
    app_account_info = indexer_client.account_info(address=app_wallet_address)
    app_algo_balance = app_account_info['account']['amount']

    # Read the global state of the application
    global_state = app_client.get_application_state()

    # acc balance + custodial deposit - minBalance
    opt_app_algo_balance = app_algo_balance + global_state.get("GLOBAL_CUSTODIAL_DEPOSIT") - 1e6

    if int(opt_app_algo_balance) == TEN_BILLION:
        return opt_amt * 1e6  # 1:1 exchange rate
    else:
        return int(int(opt_amt) * int(opt_app_algo_balance) * int(1e6) / (TEN_BILLION - int(opt_holding_of_app)))


# Find and withdraw from each custodial wallet(s) 10000 ALGO's. Returns if enough wallets
# are not available to withdraw from (which shouldn't happen).
# NOTE: withdraw amount is in microAlgos
def withdraw_from_custodial_wallets(sender_wallet, app_id, withdraw_amt):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # extract custodial wallets from indexer, from which we will withdraw 10000 ALGO's
    custodial_wallet_orig = utils.common_functions.get_custodian_wallets(app_id, {'deposited': 10000})


