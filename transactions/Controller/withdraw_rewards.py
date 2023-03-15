from algosdk import encoding, atomic_transaction_composer, transaction, logic
import API
from contract.application import Optimum
from beaker import client
import utils

# Connect to Algod-Client and Indexer-Client in Testnet Network
algod_client = API.connection.algo_conn("testnet")
indexer_client = API.connection.connect_indexer('testnet')
# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = atomic_transaction_composer.AccountTransactionSigner("a" * 32)


# Returns a list of custodial wallet addresses whose balance is above 10000 ALGO.
# Inspiration: to take back the rewards gained by wallets during governance.
# + Each account must be whitelisted and rekeyed to the optimum app.
# + Each account must be registered and has voted to governance.
# + We use the indexer to query all accounts opted in & rekeyed to app
def get_custodial_wallets_with_extra_bal(app_id):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    res = indexer_client.accounts(
        application_id=app_id, auth_addr=logic.get_application_address(app_id)
    )

    custodial_wallets = [], amts_to_withdraw = []
    for account in res.accounts:
        local_state = app_client.get_account_state(account.address, app_id)
        if local_state == {}:
            continue

        whitelisted = local_state.get('LOCAL_WHITELISTED')
        registered = local_state.get('LOCAL_REGISTERED')
        voted = local_state.get('LOCAL_VOTED')

        # DOUBT: Should if includes, "and registered and voted"?
        if whitelisted == 1:
            bal = int(account.amount - (10000e6 + 0.5e6))
            print("balance ", bal)

            if bal > 0:
                custodial_wallets.append(account.address)
                amts_to_withdraw.append(bal)

    return [custodial_wallets, amts_to_withdraw]


# Find and withdraw from each custodial wallet(s) 10000 ALGO's. Returns if enough wallets
# are not available to withdraw from (which shouldn't happen).
# NOTE: withdraw amount is in microAlgos
def withdraw_rewards_from_custodial_wallets(sender_wallet, app_id, custodial_wallets, amts_to_withdraw):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # split whole custodial wallets array & amts array into chunks of 4
    # as max 4 accounts can be passed in a tx group.
    txn_account_array = utils.common_functions.chunky_array(custodial_wallets, 4)
    txn_app_args_arrays = utils.common_functions.chunky_array(amts_to_withdraw, 4)

    # let's make the transaction objects
    txn_array = []
    atc = atomic_transaction_composer.AtomicTransactionComposer()
    j = 0

    for i in range(0, len(custodial_wallets), 4):
        # make params for each transaction
        params = algod_client.suggested_params()
        params.fee = 1000 * (len(txn_account_array[j]) if txn_account_array[j] else 0)

        # make the txn object
        app_client.add_method_call(
            atc=atc,
            method=Optimum.custodial_withdraw_rewards,
            sender=sender_wallet,
            accounts=[txn_account_array[j]],
            method_args=[list(map(lambda arg: f'int:{arg}', txn_app_args_arrays[j]))]
        )

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



