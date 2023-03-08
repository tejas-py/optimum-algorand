from algosdk.atomic_transaction_composer import *
from algosdk import account, mnemonic, logic
import connection
import application
from beaker import client

# get the account from sandbox
ACCOUNT_MNEMONIC = "direct accuse degree cloud split sunny account engage rain hub inform blind attack million museum shrug again remember radio obtain wrestle circle town able blue"
ACCOUNT_SECRET = mnemonic.to_private_key(ACCOUNT_MNEMONIC)
ACCOUNT_ADDRESS = account.address_from_private_key(ACCOUNT_SECRET)
ACCOUNT_SIGNER = AccountTransactionSigner(ACCOUNT_SECRET)

# Get algod client
algod_client = connection.algo_conn("testnet")

# app if of the application
APP_ID = 0


def app(app_id: int = 0):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=application.Optimum(), signer=ACCOUNT_SIGNER
    )

    if app_id == 0:
        app_id, app_addr, Txid = app_client.create()
        print(f"Created app at \n Application-id: {app_id},\n Application-address:{app_addr}\n and Transaction-id:{Txid}")
        app_client.fund(5 * int(1e6))
        print("Funded app")
        app_client.opt_in()
        print("Opted in")
    else:
        app_addr = logic.get_application_address(app_id)

    print(f"Current app state:{app_client.get_application_state()}")

    print(f"Current Account State:{app_client.get_account_state()}")


    # # Create an Application client
    # app_client = client.ApplicationClient(client=sandbox_client, app=Optimum(version=8), signer=account.signer)
    #
    # # Create Commitment
    # app_id, app_addr, txid = app_client.create()
    # print(
    #     f"""Deployed app in txid {txid}
    #     App ID: {app_id}
    #     App Address: {app_addr}
    # """)
    #
    # txid = app_client.call(Optimum.VRF, foreign_apps=[110096026])
    # print(txid.tx_id)
    # print(txid.return_value)
    # fund the smart contract


if __name__ == "__main__":
    app(app_id=APP_ID)
