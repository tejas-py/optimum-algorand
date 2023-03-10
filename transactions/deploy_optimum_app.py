from algosdk.atomic_transaction_composer import AtomicTransactionComposer, AccountTransactionSigner, TransactionWithSigner, transaction
from algosdk import account, mnemonic
import connection
import application
from beaker import client

# get the account (ADMIN ACCOUNT)
ACCOUNT_MNEMONIC = "direct accuse degree cloud split sunny account engage rain hub inform blind attack million museum shrug again remember radio obtain wrestle circle town able blue"
ACCOUNT_SECRET = mnemonic.to_private_key(ACCOUNT_MNEMONIC)
ACCOUNT_ADDRESS = account.address_from_private_key(ACCOUNT_SECRET)
ACCOUNT_SIGNER = AccountTransactionSigner(ACCOUNT_SECRET)
# also add the fee account

# Get algod client
algod_client = connection.algo_conn("testnet")


def deploy(OPT_asset_id):

    # Create an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=application.Optimum(), signer=ACCOUNT_SIGNER
    )

    # Deploy the Application
    app_id, app_addr, Txid = app_client.create()
    print(f"Created app at \n Application-id: {app_id},\n Application-address:{app_addr}\n and Transaction-id:{Txid}")

    # Fund the Application with 1 Algo
    app_client.fund(int(1e6))
    print("Funded app")

    # Optin to ASA by Application
    params = algod_client.suggested_params()
    params.fee = 2000
    params.flat_fee = True
    txn_details = app_client.call(
        application.Optimum.opt_in_asa,
        ACCOUNT_ADDRESS,
        suggested_params=params,
        foreign_assets=[OPT_asset_id]
    )
    print("Transaction id:", txn_details.tx_id)

    # get the OPT Balance of the admin account
    wallet_information = algod_client.account_asset_info(ACCOUNT_ADDRESS, OPT_asset_id)
    OPT_asset_holding_amount = wallet_information['asset-holding']['amount']

    # transfer all the OPT Balance to the Application
    params_transfer = algod_client.suggested_params()
    atc_transfer = AtomicTransactionComposer()
    atc_transfer.add_transaction(
        TransactionWithSigner(
            txn=transaction.AssetTransferTxn(
                ACCOUNT_ADDRESS,
                params_transfer,
                app_addr,
                OPT_asset_holding_amount,
                OPT_asset_id
            ),
            signer=ACCOUNT_SIGNER
        )
    )
    atc_transfer.submit(algod_client)
    print("Transfer Transaction id:", atc_transfer.tx_ids)

    # optin to Optimum Application by fee account
    txn_details = app_client.opt_in()  # optin by fee account, make another client object for the fee account
    print('App Optin Transaction id:', txn_details)

    # Optin to OPT ASA by fee account
    params_optin = algod_client.suggested_params()
    atc_optin = AtomicTransactionComposer()
    atc_optin.add_transaction(
        TransactionWithSigner(
            txn=transaction.AssetTransferTxn(
                ACCOUNT_ADDRESS,  # change to fee account
                params_optin,
                ACCOUNT_ADDRESS,  # change to fee account
                0,
                OPT_asset_id
            ),
            signer=ACCOUNT_SIGNER  # change to fee account
        )
    )
    atc_optin.submit(algod_client)
    print("ASA Optin Transaction id:", atc_optin.tx_ids)


if __name__ == "__main__":
    deploy()

