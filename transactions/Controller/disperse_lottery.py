from algosdk import encoding, atomic_transaction_composer, transaction
import utils.common_functions
from contract.application import Optimum
from beaker import client


# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = atomic_transaction_composer.AccountTransactionSigner("a" * 32)

# vrf application id for mainnet and testnet
vrf_app_id = {'testnet': 110096026, 'mainnet': 947957720}


# Get the Random value by calling the VRF Function in the Smart Contract
def get_random_value(algod_client, app_id, wallet_address):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # get the params for the transaction
    params = algod_client.suggested_params()
    params.fee = 2000
    params.flat_fee = True

    # get the network address
    network_address = algod_client.algod_address

    # get the current node
    if network_address == "https://testnet-algorand.api.purestake.io/ps2":
        node_network = "testnet"
    elif network_address == "https://mainnet-algorand.api.purestake.io/ps2":
        node_network = "mainnet"
    else:
        node_network = ""

    # build the transaction
    atc = atomic_transaction_composer.AtomicTransactionComposer()
    app_client.add_method_call(
        atc=atc,
        method=Optimum.VRF,
        sender=wallet_address,
        suggested_params=params,
        foreign_apps=vrf_app_id[node_network]
    )

    # extract the transaction from the ATC
    txn_details = atc.txn_list[0].txn
    result = [{'txn': encoding.msgpack_encode(txn_details)}]

    return result


# Search the Account's local state OPT Balance in the Application
def local_opt_balance(algod_client, indexer_client, app_id):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # search all accounts that are associated with the Optimum application
    all_accounts = indexer_client.accounts(application_id=app_id)

    # create a blank array
    local_opt_balances = {}

    # Check the account local state in the application
    for account in all_accounts['accounts'][0]:
        account_local_state = app_client.get_account_state(account)
        if account_local_state is None:
            continue

        # Local OPT Balance in User Account
        local_opt_amount = account_local_state.get('LOCAL_OPT_AMOUNT')
        if local_opt_amount and local_opt_amount > 0:
            local_opt_balances[account['address']] = local_opt_amount

    return local_opt_balances


# get the winner and reward amount
def get_winner_and_reward_amt(algod_client, indexer_client, app_id, vrf_random_number):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # get the app global state
    app_global_state = app_client.get_application_state()

    reward_rate_number = app_global_state.get('GLOBAL_GOVERNANCE_REWARD_RATE_NUMBER')
    reward_rate_decimals = app_global_state.get('GLOBAL_GOVERNANCE_REWARD_RATE_DECIMALS')

    if reward_rate_decimals == 0:
        apy = reward_rate_number
    else:
        apy = (reward_rate_number * 1.0)/reward_rate_decimals

    # get the account's local state opt balance
    app_local_opt_balance = local_opt_balance(algod_client, indexer_client, app_id)

    # Get the total OPT ASA Amount in the Smart Contract local State
    total_opt = 0.0
    for v in list(app_local_opt_balance.values()):
        total_opt += v

    # Find the Probability of every value
    probabilities = []
    for v in list(app_local_opt_balance.values()):
        probabilities.append(round(float(v) / total_opt, 3))

    # get the probability for every address
    cnt = len(app_local_opt_balance)
    results = []
    for i in range(1, cnt+1):
        results.append(i)

    # Get the winner of the Lottery
    s = 0
    last_index = len(probabilities) - 1

    random_number = results[last_index]

    for i in range(last_index):
        s += probabilities[i]
        if vrf_random_number < s:
            random_number = results[i]
            break

    weeks = 13

    # this would be the reward we would get after each governance period
    reward = total_opt * apy

    reward_per_week = round(float(reward/weeks), 5)
    addresses = list(app_local_opt_balance.keys())
    return [addresses[random_number-1], reward_per_week]


# Get the vrf number from the transaction id
def reveal_vrf_number(indexer_client, vrf_txn_id):

    # get the vrf number from the transaction id
    vrf_number = utils.common_functions.random_value_by_vrf(indexer_client, vrf_txn_id)

    return {'message': vrf_number}


# transfer 0 amount to admin and pass the vrf number as the transaction note
def send_vrf_number_to_admin(algod_client, admin_wallet, vrf_number):

    # set the params
    atc = atomic_transaction_composer.AtomicTransactionComposer()
    params = algod_client.suggested_params()

    # make transaction object
    atc.add_transaction(atomic_transaction_composer.TransactionWithSigner(
        txn=transaction.PaymentTxn(
            admin_wallet,
            params,
            admin_wallet,
            0,
            note=vrf_number
        ),
        signer=ACCOUNT_SIGNER
    ))

    # get the txn object
    txn_object = atc.txn_list[0].txn

    # encode the transaction
    result = [{'txn': encoding.msgpack_encode(txn_object)}]

    return result
