from algosdk.atomic_transaction_composer import AtomicTransactionComposer, AccountTransactionSigner
from algosdk import encoding
from connection import algo_conn, connect_indexer
from application import Optimum
from beaker import client

# Connect to Algod-Client in Testnet Network
algod_client = algo_conn("testnet")
indexer_client = connect_indexer("testnet")
# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = AccountTransactionSigner("a" * 32)


# Get the Random value by calling the VRF Function in the Smart Contract
def get_random_value(app_id, wallet_address):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    params = algod_client.suggested_params()
    params.fee = 2000
    params.flat_fee = True

    # build the transaction
    atc = AtomicTransactionComposer()
    app_client.add_method_call(
        atc=atc,
        method=Optimum.VRF,
        sender=wallet_address,
        suggested_params=params,
        foreign_apps=[110096026]
    )

    # extract the transaction from the ATC
    txn_details = atc.txn_list[0]
    result = [{'txn': encoding.msgpack_encode(txn_details.txn)}]

    return result


# Search the Account's local state OPT Balance in the Application
def local_opt_balance(app_id):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # search all accounts that are associated with the Optimum application
    all_accounts = indexer_client.accounts(application_id=app_id)

    # create a blank array
    local_opt_balances = {}

    # Check the account local state in the application
    for account in all_accounts.accounts:
        account_local_state = app_client.get_account_state(account)
        if account_local_state is None:
            continue

        # Local OPT Balance in User Account
        local_opt_amount = account_local_state.get('LOCAL_OPT_AMOUNT')
        if local_opt_amount and local_opt_amount > 0:
            local_opt_balances[account.address] = local_opt_amount

    return local_opt_balances


#
def get_winner_and_reward_amt(app_id, admin_wallet, vrf_random_number):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # get the app global state
    app_global_state = app_client.get_application_state()
    print("Application Global State:", app_global_state)

    reward_rate_number = app_global_state.get('GLOBAL_GOVERNANCE_REWARD_RATE_NUMBER')
    reward_rate_decimals = app_global_state.get('GLOBAL_GOVERNANCE_REWARD_RATE_DECIMALS')

    if reward_rate_decimals == 0:
        apy = reward_rate_number
    else:
        apy = (reward_rate_number * 1.0)/reward_rate_decimals

    # get the account's local state opt balance
    app_local_opt_balance = local_opt_balance(app_id)

    # Get the total OPT ASA Amount in the Smart Contract local State
    total_opt = 0.0
    for v in app_local_opt_balance.values():
        total_opt += v

    # Find the Probability of every value
    probabilities = []
    for v in app_local_opt_balance.values():
        probabilities.append(round(float(v) / total_opt, 3))

