from algosdk import encoding, atomic_transaction_composer, transaction, logic
from contract.application import Optimum
from beaker import client
import utils

# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = atomic_transaction_composer.AccountTransactionSigner("a" * 32)


def deposit(algod_client, sender_wallet, app_id, asset_id, algo_amt):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # deposit ALGO to the contract, receive OPT
    atc = atomic_transaction_composer.AtomicTransactionComposer()

    # Transaction 1: Pay algos to smart contract
    params_txn1 = algod_client.suggested_params()
    app_client.add_transaction(
        atc=atc,
        txn=transaction.PaymentTxn(
            sender=sender_wallet,
            sp=params_txn1,
            receiver=logic.get_application_address(app_id),
            amt=algo_amt
        )
    )

    # Transaction 2: Receive OPT, call the Optimum Application
    params_txn2 = algod_client.suggested_params()
    params_txn2.fee = 2000
    app_client.add_method_call(
        atc=atc,
        method=Optimum.exchange,
        sender=sender_wallet,
        suggested_params=params_txn2,
        foreign_assets=[asset_id]
    )

    # fetch the transaction objects
    txn_1 = atc.txn_list[0].txn
    txn_2 = atc.txn_list[1].txn

    # Group Transactions
    print("Grouping transactions...")
    group_id = transaction.calculate_group_id([txn_1, txn_2])
    print("...computed groupId: ", group_id)
    txn_1.group = group_id
    txn_2.group = group_id

    txn_grp = [{'txn': encoding.msgpack_encode(txn_1)},
               {'txn': encoding.msgpack_encode(txn_2)}]

    return txn_grp


# Find and fund custodial wallets with 10000 ALGO increments.
# Returns if enough wallets are not available.
# NOTE: deposit amount is in microAlgos
def fund_custodian_wallets(algod_client, indexer_client, sender_wallet, app_id, deposit_amt):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # extract custodial wallets from indexer, which we will fund
    custodial_wallets_orig = utils.common_functions.get_custodian_wallets(algod_client, indexer_client, app_id, {'deposited': 0})

    req_wallets = int(deposit_amt/10000e6)
    if len(custodial_wallets_orig) < req_wallets:
        return {'message': f"Not enough wallets to fund."
                           f"Required ${req_wallets} but got ${custodial_wallets_orig.length}."
                           f"Please generate more accounts"}, 400

    # we only get address we need
    custodial_wallets = custodial_wallets_orig[0:req_wallets]

    # split whole custodial wallets array into chunks of 4
    # as max 4 accounts can be passed in a tx group.
    txn_account_array = utils.common_functions.chunky_array(custodial_wallets, 4)

    # create a for loop for transaction objects
    txn_array = []
    j = 0

    for i in range(0, req_wallets, 4):
        # make params for each transaction
        params = algod_client.suggested_params()
        params.fee = 1000 * (len(txn_account_array[j]) if txn_account_array[j] else 0)

        # make transaction object
        atc = atomic_transaction_composer.AtomicTransactionComposer()
        app_client.add_method_call(
            atc=atc,
            method=Optimum.custodial_deposit,
            sender=sender_wallet,
            accounts=[txn_account_array[j]]
        )
        # push the txn object into the transaction array
        txn_array.append(atc.txn_list[0].txn)
        j += 1

    # Assemble the transactions in group of 16, and pass return the transaction object
    txn_groups = utils.common_functions.chunky_array(txn_array, 16)

    # Assign group id to the group transactions
    group_id_transactions = []
    for txn_group in txn_groups:
        txns = transaction.assign_group_id(txn_group)
        group_id_transactions.append(txns)

    # Encode the transactions to return it
    encoded_txns = []
    for single_group_txn in group_id_transactions:
        txn_grp = []
        for single_txn in single_group_txn:
            encoded_txn = {'txn': encoding.msgpack_encode(single_txn)}
            txn_grp.append(encoded_txn)
        encoded_txns.append(txn_grp)

    return encoded_txns
