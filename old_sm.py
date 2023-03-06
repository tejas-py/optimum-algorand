import sys
sys.path.insert(0,'.')

from algobpy.parse import parse_params
from pyteal import *


# --- State ---

# Global
GLOBAL_ADMIN: TealType.bytes = Bytes("admin") # admin address
GLOBAL_PAUSED: TealType.uint64 = Bytes("paused") # global pause state

# "count" at which governance we're on.
GLOBAL_GOVERNANCE_NONCE: TealType.uint64 = Bytes("gov_nonce")
GLOBAL_PERIOD_START: TealType.uint64 = Bytes("period_start") # perid start
GLOBAL_REWARD_DISTRIBUTION: TealType.uint64 = Bytes("reward_distribution") # reward distribution
GLOBAL_REGISTRATION_END: TealType.uint64 = Bytes("registration_end") # registration end
GLOBAL_PERIOD_END: TealType.uint64 = Bytes("period_end") # period end
GLOBAL_CUSTODIAL_DEPOSIT: TealType.uint64 = Bytes("cust_dep") # total Algo's deposited in "whitelisted" custodial wallets
GLOBAL_GOVERNANCE_REWARD_RATE_NUMBER: TealType.uint64 = Bytes("reward_rate_no") # governance reward rate number (apy) (set by admin)
GLOBAL_GOVERNANCE_REWARD_RATE_DECIMALS: TealType.uint64 = Bytes("reward_rate_decimals") # governance reward rate decimals (apy) (set by admin)

# tracking balances to make deposit rate constant at each period
GLOBAL_TOTAL_OPT_DISPERSED_AT_GOVERNANCE: TealType.uint64 = Bytes("total_opt_dispersed_at_governance") # total OPT dispersed by the contract (tracked during each governance period)
GLOBAL_APP_BALANCE_AT_GOVERNANCE: TealType.uint64 = Bytes("app_balance_at_governance") # app balance (tracked during each governance period)

# track time for last lottery dispersal
GLOBAL_LAST_LOTTERY_DISPERSAL_TS: TealType.uint64 = Bytes("lst_lott_dispersal_ts")


# Local
LOCAL_WHITELISTED: TealType.uint64 = Bytes("whitelisted") # custodial wallet whitelist status
LOCAL_DEPOSITED: TealType.uint64 = Bytes("deposited") # amount deposited to "this" custodial wallet
LOCAL_REGISTERED: TealType.uint64 = Bytes("registered") # is wallet registered for governance := 0/1
LOCAL_VOTED: TealType.uint64 = Bytes("voted") # has wallet voted for a governance option(s) := 0/1
LOCAL_OPT_AMOUNT: TealType.uint64 = Bytes("local_opt_amt") # local OPT amount in user's wallet (tracked for dispersing lottery)
LOCAL_OPT_REWARD_AMOUNT: TealType.uint64 = Bytes("local_opt_reward_amt") # local OPT amount in user's wallet which he won in lottery (reward)

# store "count" at which governance we're on in the fee account's local state
# (to prevent double fee collection at a single governance period)
LOCAL_GOVERNANCE_NONCE: TealType.uint64 = Bytes("gov_nonce")

# constants
ACCOUNT_MIN_BALANCE = Int(10_00_000) # Setting min balance of app account as 1 ALGO
TEN_BILLION = Int(10_000_000_000 * 1_000_000)

# returns Algo's held "by" the contracts + Algo's deposited in custodial wallets
def appBalance():
    return ((Balance(Global.current_application_address()) + App.globalGet(GLOBAL_CUSTODIAL_DEPOSIT)) - ACCOUNT_MIN_BALANCE)

def governanceNonce():
    return App.globalGet(GLOBAL_GOVERNANCE_NONCE)

# --- Helper Functions ---
@Subroutine(TealType.uint64)
def basic_checks(tx_idx):
    """
    Txn common checks (rekey, close_rem_to, asset_close_to)
    """
    return And(
        Gtxn[tx_idx].rekey_to() == Global.zero_address(),
        Gtxn[tx_idx].close_remainder_to() == Global.zero_address(),
        Gtxn[tx_idx].asset_close_to() == Global.zero_address()
    )


@Subroutine(TealType.none)
def assert_sender_admin():
    """
    Asserts txn.sender is admin
    """
    return Assert(
        And(
            basic_checks(Int(0)),
            Txn.sender() == App.globalGet(GLOBAL_ADMIN)
        )
    )

def now(): return Global.latest_timestamp()

@Subroutine(TealType.none)
def handle_deposit(opt_asa_id):
    """
    Handles deposit of ALGO in exchange of OPT. Must be during
    [reward_distribution, registration_end]
    """
    optBalOfAppAcc = AssetHolding.balance(
        Global.current_application_address(),
        opt_asa_id
    )

    scratch_amount = ScratchVar(TealType.uint64)
    def saveAmount(amount): return scratch_amount.store(amount)
    def amount(): return scratch_amount.load()

    return Seq([
        optBalOfAppAcc,
        Assert(
            And(
                Txn.assets[0] == opt_asa_id,
                # reward_distribution <= now <= registration_end (deposit window)
                App.globalGet(GLOBAL_REWARD_DISTRIBUTION) <= now(),
                now() <= App.globalGet(GLOBAL_REGISTRATION_END),
                )
        ),
        If(Or(optBalOfAppAcc.value() == TEN_BILLION, governanceNonce() <= Int(1)))
        .Then(saveAmount(Gtxn[0].amount())) # since algo amt is in micro algos
        .Else(
            saveAmount(
                (
                        (Gtxn[0].amount() * App.globalGet(GLOBAL_TOTAL_OPT_DISPERSED_AT_GOVERNANCE)) /
                        (App.globalGet(GLOBAL_APP_BALANCE_AT_GOVERNANCE))
                )
            )
        ),

        # inner tx sending Optimum ASA to user (amount calculated above)
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: opt_asa_id,
                TxnField.asset_receiver: Txn.sender(),
                TxnField.asset_amount: amount(),
                # fee is set externally
                TxnField.fee: Int(0)
            }
        ),
        InnerTxnBuilder.Submit(),

        # update local opt amount deposited to user
        App.localPut(
            Txn.sender(),
            LOCAL_OPT_AMOUNT,
            App.localGet(Txn.sender(), LOCAL_OPT_AMOUNT) + amount()
        )
    ])


@Subroutine(TealType.none)
def handle_withdraw(opt_asa_id, fee_addr):
    """
    Handles withdrawal of ALGO in exchange of OPT. Can be during any time.
    """
    optBalOfAppAcc = AssetHolding.balance(
        Global.current_application_address(),
        opt_asa_id
    )

    scratch_amount = ScratchVar(TealType.uint64)
    def saveAmount(amount): return scratch_amount.store(amount)
    def amount(): return scratch_amount.load()

    return Seq([
        optBalOfAppAcc,
        Assert(
            And(
                Gtxn[0].xfer_asset() == opt_asa_id,
                Gtxn[0].asset_amount() > Int(0)
            )
        ),
        saveAmount(
            # note we do "- Gtxn[0].asset_amount()" in denominator because app account has already accepted OPT
            # in tx0, which we want to avoid in "current" exchange calculation
            (((Gtxn[0].asset_amount() * appBalance())) / (TEN_BILLION - (optBalOfAppAcc.value() - Gtxn[0].asset_amount())))
        ),

        # first deposit .1% fee to the fee address
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.Payment,
                TxnField.receiver: fee_addr,
                TxnField.amount: amount() / Int(1000), # algoWithdrawAmount * .001 (0.1% fee)
                # fee is set externally
                TxnField.fee: Int(0)
            }
        ),
        InnerTxnBuilder.Submit(),

        # inner tx sending remaining ALGO to user (amount calculated above)
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.Payment,
                TxnField.receiver: Txn.sender(),
                TxnField.amount: amount() - (amount() / Int(1000)),
                # fee is set externally
                TxnField.fee: Int(0)
            }
        ),
        InnerTxnBuilder.Submit(),

        # update local opt amount (OPT is deducted from user)
        If(App.localGet(Txn.sender(), LOCAL_OPT_AMOUNT) >= Gtxn[0].asset_amount())
        .Then(
            App.localPut(
                Txn.sender(),
                LOCAL_OPT_AMOUNT,
                App.localGet(Txn.sender(), LOCAL_OPT_AMOUNT) - Gtxn[0].asset_amount()
            )
        ),
    ])

def approval_program(ARG_OPT_ASSET_INDEX, ARG_FEE_ADDRESS):
    """
    Optiimum App
    Commands:
        pause_app                pause app (only by admin)
        unpause_app              unpause app (only by admin)
        opt_in_asa               Opts In Optimum ASA to App account
        exchange                 Exchange ALGO for OPT & vice versa
    """

    is_admin = Txn.sender() == App.globalGet(GLOBAL_ADMIN)

    # initialization
    # Expected arguments:
    # * appArgs: []
    on_initialize = Seq([
        App.globalPut(GLOBAL_ADMIN, Txn.accounts[1]),
        App.globalPut(GLOBAL_GOVERNANCE_NONCE, Int(0)),
        Return(Int(1))
    ])

    # Pause all operations (callable only by admin)
    pause_app = Seq([
        assert_sender_admin(),
        App.globalPut(GLOBAL_PAUSED, Int(1)),
        Return(Int(1))
    ])

    # resume all operations (callable only by admin)
    unpause_app = Seq([
        assert_sender_admin(),
        App.globalPut(GLOBAL_PAUSED, Int(0)),
        Return(Int(1))
    ])

    # loads optimum ASA balance of the optimum app account (0 or 1)
    opt_app_holding = AssetHolding.balance(
        Global.current_application_address(), Int(ARG_OPT_ASSET_INDEX))

    # "Register" each to custodial wallets (passed in txn.accounts) by the contract.
    # Must be called by admin and each wallet must be whitelisted first.
    # Expected arguments:
    # * accounts: [...custodial wallet addresses]
    # * appArgs: [governance_wallet_addr, registration memo]
    set_governance_timelines = Seq([
        opt_app_holding,
        assert_sender_admin(),
        Assert(
            And(
                # GLOBAL_REGISTRATION_END must be > GLOBAL_REWARD_DISTRIBUTION
                Btoi(Txn.application_args[3]) > Btoi(Txn.application_args[2]),
                # Period End > Period Start
                Btoi(Txn.application_args[4]) > Btoi(Txn.application_args[1]),
                )
        ),
        App.globalPut(GLOBAL_PERIOD_START, Btoi(Txn.application_args[1])),
        App.globalPut(GLOBAL_REWARD_DISTRIBUTION, Btoi(Txn.application_args[2])),
        App.globalPut(GLOBAL_REGISTRATION_END, Btoi(Txn.application_args[3])),
        App.globalPut(GLOBAL_PERIOD_END, Btoi(Txn.application_args[4])),
        App.globalPut(GLOBAL_GOVERNANCE_NONCE, governanceNonce() + Int(1)),

        # tracked during each governance, to keep the deposit rate "static" during each period
        If(governanceNonce() > Int(1)) # exchange rate is 1:1 during each governance period
        .Then(
            Seq([
                App.globalPut(GLOBAL_TOTAL_OPT_DISPERSED_AT_GOVERNANCE, (TEN_BILLION - opt_app_holding.value())),
                App.globalPut(GLOBAL_APP_BALANCE_AT_GOVERNANCE, appBalance()),
            ])
        ),
        Return(Int(1))
    ])

    # Sets the reward rate for the governance. Must be called by admin.
    # Expected arguments:
    # * appArgs: [reward_rate_number, reward_rate_decimals] eg. [2, 1000] means 0.2% (since x% == x/100)
    set_governance_reward_rate = Seq([
        assert_sender_admin(),
        Assert(
            # ensure max reward rate is <= 0.2% for the week (or 20% if multiplied by 100)
            # so (x/decimal_places) * 100 = x%
            # (multiplying by extra 100 so 0.2 comes out as 20)
            ((Btoi(Txn.application_args[1]) * Int(100) * Int(100) ) / Btoi(Txn.application_args[2])) <= Int(20)
        ),
        App.globalPut(GLOBAL_GOVERNANCE_REWARD_RATE_NUMBER, Btoi(Txn.application_args[1])),
        App.globalPut(GLOBAL_GOVERNANCE_REWARD_RATE_DECIMALS, Btoi(Txn.application_args[2])),
        Return(Int(1))
    ])

    # Opts In Optimum App to the optimum ASA (asa_id passed as first foreign asset).
    # Rejects if asa_id is incorrect,
    # or optimum ASA is already optedin. Expected arguments:
    # - opt_asa_id: passed as first foreign asset
    opt_in_asa = Seq([
        opt_app_holding,
        # verify TOKEN_OUT ASA not opted in
        Assert(
            And(
                Global.group_size() == Int(1),
                basic_checks(Int(0)),
                Int(ARG_OPT_ASSET_INDEX) == Txn.assets[0],
                opt_app_holding.hasValue() == Int(0), # if true then asa not opted in
            )
        ),
        # submit opt-in transaction by App
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: Int(ARG_OPT_ASSET_INDEX),
                TxnField.asset_receiver: Global.current_application_address(),
                TxnField.asset_amount: Int(0),
                # fee is set externally
                TxnField.fee: Int(0)
            }
        ),
        InnerTxnBuilder.Submit(),
        Return(Int(1))
    ])

    # Whitelist account by the contract. If whitelisted, account can
    # now act as our custodial wallet.
    whitelist_acc = Seq([
        Assert(
            And(
                Txn.close_remainder_to() == Global.zero_address(),
                Txn.asset_close_to() == Global.zero_address(),
                # imp_check: only proceed with whitelisting if acc is being rekeyed to the smart contract
                Txn.rekey_to() == Global.current_application_address()
            )
        ),
        # whitelist account, set 0 deposit amount
        App.localPut(Txn.sender(), LOCAL_WHITELISTED, Int(1)),
        App.localPut(Txn.sender(), LOCAL_DEPOSITED, Int(0)),
        App.localPut(Txn.sender(), LOCAL_REGISTERED, Int(0)),
        App.localPut(Txn.sender(), LOCAL_VOTED, Int(0)),
        Return(Int(1))
    ])

    # counters used in For loop below
    i = ScratchVar(TealType.uint64) # txn.accounts counter

    # Deposit 10000 ALGO each to custodial wallets (passed in txn.accounts) by the contract.
    # Must be called by admin. Expected arguments:
    # * accounts: [...custodial wallet addresses]
    custodial_deposit = Seq([
        # verify: sender is admin, and other basic checks
        Assert(
            And(
                basic_checks(Txn.group_index()),
                Txn.sender() == App.globalGet(GLOBAL_ADMIN),
                )
        ),
        # Now, for each txn.account of current transaction, deposit 10000 ALGO (after verification)
        For(i.store(Int(1)), i.load() <= Txn.accounts.length(), i.store(i.load() + Int(1))).Do(
            Seq([
                # for each account, verify that it's whitelisted and no amount is deposited yet
                Assert(
                    And(
                        App.localGet(Txn.accounts[i.load()], LOCAL_WHITELISTED) == Int(1),
                        App.localGet(Txn.accounts[i.load()], LOCAL_DEPOSITED) == Int(0)
                    )
                ),

                # send 10000 ALGO to each Txn.account
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.Payment,
                        TxnField.receiver: Txn.accounts[i.load()],
                        TxnField.amount: Int(10000 * 1000000), # 10000e6 micro algos
                        # fee is set externally
                        TxnField.fee: Int(0)
                    }
                ),
                InnerTxnBuilder.Submit(),

                # update {local, global} state
                App.localPut(Txn.accounts[i.load()], LOCAL_DEPOSITED, Int(10000)),
                # deposit += 10000. NOTE: in global state we store amount in "micro algo's"
                App.globalPut(GLOBAL_CUSTODIAL_DEPOSIT, App.globalGet(GLOBAL_CUSTODIAL_DEPOSIT) + Int(10000 * 1000000)),
            ])
        ),
        Return(Int(1))
    ])


    # Withdraw 10000 ALGO each from custodial wallets (passed in txn.accounts) by the contract.
    # Expected arguments:
    # * accounts: [...custodial wallet addresses]
    custodial_withdraw = Seq([
        # verify: basic checks
        Assert(basic_checks(Txn.group_index())),
        # Now, for each txn.account of current transaction, withdraw 10000 ALGO (after verification)
        For(i.store(Int(1)), i.load() <= Txn.accounts.length(), i.store(i.load() + Int(1))).Do(
            Seq([
                # for each account, verify that it's whitelisted 10000 ALGO is deposited
                Assert(
                    And(
                        App.localGet(Txn.accounts[i.load()], LOCAL_WHITELISTED) == Int(1),
                        App.localGet(Txn.accounts[i.load()], LOCAL_DEPOSITED) == Int(10000)
                    )
                ),

                # withdraw 10000 ALGO each from Txn.account
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.Payment,
                        TxnField.sender: Txn.accounts[i.load()],
                        TxnField.receiver: Global.current_application_address(),
                        TxnField.amount: Int(10000 * 1000000), # 10000e6 micro algos
                        # fee is set externally
                        TxnField.fee: Int(0)
                    }
                ),
                InnerTxnBuilder.Submit(),

                # update {local, global} state
                App.localPut(Txn.accounts[i.load()], LOCAL_DEPOSITED, Int(0)),
                # deposit -= 10000. NOTE: in global state we store amount in "micro algo's"
                App.globalPut(GLOBAL_CUSTODIAL_DEPOSIT, App.globalGet(GLOBAL_CUSTODIAL_DEPOSIT) - Int(10000 * 1000000)),
            ])
        ),
        Return(Int(1))
    ])

    # "Register" each to custodial wallets (passed in txn.accounts) by the contract.
    # Must be called by admin and each wallet must be whitelisted first.
    # Expected arguments:
    # * accounts: [...custodial wallet addresses]
    # * appArgs: [governance_wallet_addr, registration memo]
    register_custodial_wallets = Seq([
        # verify: sender is admin, and other basic checks
        Assert(
            And(
                basic_checks(Txn.group_index()),
                now() <= App.globalGet(GLOBAL_REGISTRATION_END),
                Txn.sender() == App.globalGet(GLOBAL_ADMIN),
                )
        ),
        # Now, for each txn.account of current transaction EXCEPT the last one (as it is the
        # governance address), register the wallet
        For(i.store(Int(1)), i.load() < Txn.accounts.length(), i.store(i.load() + Int(1))).Do(
            Seq([
                # for each account, verify that it's whitelisted already & NOT registered
                Assert(
                    And(
                        App.localGet(Txn.accounts[i.load()], LOCAL_WHITELISTED) == Int(1),
                        # registered nonce should be less than "current" governance nonce, otherwise we have already registered
                        App.localGet(Txn.accounts[i.load()], LOCAL_REGISTERED) < governanceNonce()
                    )
                ),

                # register for governance: send 0 ALGO to governance wallet with a memo
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.Payment,
                        TxnField.sender: Txn.accounts[i.load()],
                        TxnField.receiver: Txn.application_args[1], # governance wallet to register
                        TxnField.amount: Int(0),
                        # note/memo field for registration. eg: af/gov1:j{"com":YYY}
                        TxnField.note: Txn.application_args[2],
                        # fee is set externally
                        TxnField.fee: Int(0)
                    }
                ),
                InnerTxnBuilder.Submit(),

                # update local state to "registered" for "current governance period"
                App.localPut(Txn.accounts[i.load()], LOCAL_REGISTERED, governanceNonce()),
            ])
        ),
        Return(Int(1))
    ])

    # "Voting" by each custodial wallets (passed in txn.accounts) by the contract.
    # Must be called by admin and each wallet must be whitelisted & registered to
    # governance first. Expected arguments:
    # * accounts: [...custodial wallet addresses]
    # * appArgs: [governance_wallet_addr, voting memo]
    vote_by_custodial_wallets = Seq([
        # verify: sender is admin, and other basic checks
        Assert(
            And(
                basic_checks(Txn.group_index()),
                Txn.sender() == App.globalGet(GLOBAL_ADMIN),
                )
        ),
        # Now, for each txn.account of current transaction EXCEPT the last one (as it is the
        # governance address), do voting by the wallet
        For(i.store(Int(1)), i.load() < Txn.accounts.length(), i.store(i.load() + Int(1))).Do(
            Seq([
                # for each account, verify that it's whitelisted already & registered AND
                # hasn't voted yet
                Assert(
                    And(
                        App.localGet(Txn.accounts[i.load()], LOCAL_WHITELISTED) == Int(1),
                        App.localGet(Txn.accounts[i.load()], LOCAL_REGISTERED) == governanceNonce(),
                        App.localGet(Txn.accounts[i.load()], LOCAL_VOTED) < governanceNonce()
                    )
                ),

                # voting for governance: send 0 ALGO to governance wallet with a memo
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.Payment,
                        TxnField.sender: Txn.accounts[i.load()],
                        TxnField.receiver: Txn.application_args[1], # governance wallet to vote
                        TxnField.amount: Int(0),
                        # note/memo field for voting. eg: af/gov1:j[5,"a"]
                        TxnField.note: Txn.application_args[2],
                        # fee is set externally
                        TxnField.fee: Int(0)
                    }
                ),
                InnerTxnBuilder.Submit(),

                # update local state to "voted" for the current governance period
                App.localPut(Txn.accounts[i.load()], LOCAL_VOTED, governanceNonce()),
            ])
        ),
        Return(Int(1))
    ])

    # Withdraw rewards from custodial wallets (passed in txn.accounts) by the contract.
    # Must be called by admin
    # Expected arguments:
    # * accounts: [...custodial wallet addresses]
    # * appArgs: [ ...amounts ]
    custodial_withdraw_rewards = Seq([
        # verify: sender is admin, and other basic checks
        Assert(
            And(
                basic_checks(Txn.group_index()),
                Txn.sender() == App.globalGet(GLOBAL_ADMIN),
                )
        ),
        # Now, for each txn.account of current transaction, withraw rewards from it (after verification)
        For(i.store(Int(1)), i.load() <= Txn.accounts.length(), i.store(i.load() + Int(1))).Do(
            Seq([
                # for each account, verify that it's whitelisted 10000 ALGO is deposited
                Assert(
                    And(
                        App.localGet(Txn.accounts[i.load()], LOCAL_WHITELISTED) == Int(1),
                        App.localGet(Txn.accounts[i.load()], LOCAL_REGISTERED) == governanceNonce(),
                        App.localGet(Txn.accounts[i.load()], LOCAL_VOTED) == governanceNonce(),

                        # Ensure that after withdrawing the reward amount from the custodial wallet
                        # 10000 ALGO + account_min_balance remains (which the user can withdraw later).
                        (Balance(Txn.accounts[i.load()]) - Btoi(Txn.application_args[i.load()])) >= (Int(10000 * 1000000))
                    )
                ),

                # withdraw rewards in ALGO each from Txn.account
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.Payment,
                        TxnField.sender: Txn.accounts[i.load()],
                        TxnField.receiver: Global.current_application_address(),
                        TxnField.amount: Btoi(Txn.application_args[i.load()]), # arg[0] is "custodial_withdraw_rewards"
                        # fee is set externally
                        TxnField.fee: Int(0)
                    }
                ),
                InnerTxnBuilder.Submit(),
            ])
        ),
        Return(Int(1))
    ])

    # "close" custodial wallets by admin. Simply rekey these accounts back to admin
    # Expected arguments:
    # * accounts: [...custodial wallet addresses]
    # * appArgs: [ ...amounts ]
    custodial_close_wallets = Seq([
        # verify: sender is admin, and other basic checks
        Assert(
            And(
                basic_checks(Txn.group_index()),
                Txn.sender() == App.globalGet(GLOBAL_ADMIN),
                )
        ),
        # Now, for each txn.account of current transaction, withraw rewards from it (after verification)
        For(i.store(Int(1)), i.load() <= Txn.accounts.length(), i.store(i.load() + Int(1))).Do(
            Seq([
                # for each account, verify that it's whitelisted
                Assert(App.localGet(Txn.accounts[i.load()], LOCAL_WHITELISTED) == Int(1)),

                # setup a tx with "rekey to" set as the admin (sender)
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.Payment,
                        TxnField.sender: Txn.accounts[i.load()],
                        TxnField.receiver: Global.current_application_address(),
                        TxnField.amount: Int(0),
                        # give control back to that account (bdw, do we really need this?)
                        TxnField.rekey_to: Txn.sender(),
                        # fee is set externally
                        TxnField.fee: Int(0)
                    }
                ),
                InnerTxnBuilder.Submit(),
            ])
        ),
        Return(Int(1))
    ])


    exchange = Seq([
        Assert(
            And(
                Global.group_size() == Int(2),
                basic_checks(Int(0)),
                basic_checks(Int(1)),
                Gtxn[0].sender() == Gtxn[1].sender(),
                Gtxn[1].type_enum() == TxnType.ApplicationCall,
                )
        ),
        If(Gtxn[0].type_enum() == TxnType.Payment)
        .Then(handle_deposit(Int(ARG_OPT_ASSET_INDEX)))

        .ElseIf(Gtxn[0].type_enum() == TxnType.AssetTransfer)
        .Then(handle_withdraw(Int(ARG_OPT_ASSET_INDEX), Addr(ARG_FEE_ADDRESS)))

        .Else(Err()),
        Return(Int(1))
    ])


    # Disperse Lottery amount to the winner address (called every week by the admin)
    # Must be called by admin.
    disperse_lottery = Seq([
        # verify: sender is admin, and other basic checks
        Assert(
            And(
                basic_checks(Txn.group_index()),
                Txn.sender() == App.globalGet(GLOBAL_ADMIN),

                # ensure atleast 23h b/w consecutive lottery dispersals
                Global.latest_timestamp() - App.globalGet(GLOBAL_LAST_LOTTERY_DISPERSAL_TS) >= Int(82800)
            )
        ),

        # deposit reward amount to the winner address (90%)
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: Int(ARG_OPT_ASSET_INDEX),
                TxnField.asset_receiver: Txn.accounts[1],
                TxnField.asset_amount: Btoi(Txn.application_args[1]),
                # fee is set externally
                TxnField.fee: Int(0)
            }
        ),
        InnerTxnBuilder.Submit(),

        # deposit reward amount to the fee wallet (10% fee)
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: Int(ARG_OPT_ASSET_INDEX),
                TxnField.asset_receiver: Addr(ARG_FEE_ADDRESS),
                TxnField.asset_amount: Btoi(Txn.application_args[2]),
                # fee is set externally
                TxnField.fee: Int(0)
            }
        ),
        InnerTxnBuilder.Submit(),

        # track last time lottery was dispersed (to ensure gap b/w consecutive lottery is atleast 23h)
        App.globalPut(
            GLOBAL_LAST_LOTTERY_DISPERSAL_TS, Global.latest_timestamp()
        ),

        # update local state to track the winner and the lottery amt (to show in table in UI)
        App.localPut(
            Txn.accounts[1],
            LOCAL_OPT_REWARD_AMOUNT,
            App.localGet(Txn.accounts[1], LOCAL_OPT_REWARD_AMOUNT) + Btoi(Txn.application_args[1])
        ),

        # update local opt amount key deposited to user (i.e track deposits + lottery winnings for a user)
        App.localPut(
            Txn.accounts[1],
            LOCAL_OPT_AMOUNT,
            App.localGet(Txn.accounts[1], LOCAL_OPT_AMOUNT) + Btoi(Txn.application_args[1])
        ),
        Return(Int(1))
    ])

    # inner transaction to get the randomness
    get_randomness = Seq(
        # Prep arguments
        (round_number := abi.Uint64()).set(Global.round() - Int(10)),
        (user_data := abi.make(abi.DynamicArray[abi.Byte])).set([]),
        InnerTxnBuilder.ExecuteMethodCall(
            app_id=Txn.applications[1],
            method_signature="must_get(uint64,byte[])byte[]",
            args=[round_number, user_data],
        ),
        # Remove first 4 bytes (ABI return prefix)
        # and return the rest
        Extract(InnerTxn.last_log(), Int(0), Int(9))
    )

    # store the randomness in the global variable
    vrf_function = Seq(
        # # Get the randomness
        (randomness_number := abi.DynamicBytes()).decode(get_randomness),
        App.globalPut(Bytes('random number'), Mod(Btoi(randomness_number.get()), Int(9999999))),
        Approve()
    )

    program = Cond(
        # Verfies that the application_id is 0, jumps to on_initialize.
        [Txn.application_id() == Int(0), on_initialize],
        # Verifies Update transaction, accepts only if sender is admin.
        [Txn.on_completion() == OnComplete.UpdateApplication, Return(is_admin)],
        # Verifies Update or delete transaction, rejects it.
        [Txn.on_completion() == OnComplete.DeleteApplication, Return(Int(0))],
        # Verifies closeout or OptIn transaction, approves it.
        [
            Or(
                Txn.on_completion() == OnComplete.CloseOut,
                Txn.on_completion() == OnComplete.OptIn
            ),
            Return(Int(1))
        ],
        # if app is paused, and sender is not admin, do not proceed.
        # So if pause has been triggerred, normal operations can resume only
        # after admin unpauses the app (by calling "unpause_app" branch)
        [
            And(
                App.globalGet(GLOBAL_PAUSED) == Int(1),
                Txn.sender() != App.globalGet(GLOBAL_ADMIN),
                ),
            Err()
        ],
        [Txn.application_args[0] == Bytes("pause_app"), pause_app],
        [Txn.application_args[0] == Bytes("unpause_app"), unpause_app],
        [Txn.application_args[0] == Bytes("set_governance_timelines"), set_governance_timelines],
        [Txn.application_args[0] == Bytes("set_governance_reward_rate"), set_governance_reward_rate],
        [Txn.application_args[0] == Bytes("whitelist_acc"), whitelist_acc],
        [Txn.application_args[0] == Bytes("custodial_deposit"), custodial_deposit],
        [Txn.application_args[0] == Bytes("custodial_withdraw"), custodial_withdraw],
        [Txn.application_args[0] == Bytes("opt_in_asa"), opt_in_asa],
        [Txn.application_args[0] == Bytes("exchange"), exchange],
        [Txn.application_args[0] == Bytes("register_custodial_wallets"), register_custodial_wallets],
        [Txn.application_args[0] == Bytes("vote_by_custodial_wallets"), vote_by_custodial_wallets],
        [Txn.application_args[0] == Bytes("custodial_withdraw_rewards"), custodial_withdraw_rewards],
        [Txn.application_args[0] == Bytes("custodial_close_wallets"), custodial_close_wallets],
        [Txn.application_args[0] == Bytes("disperse_lottery"), disperse_lottery],
        [Txn.application_args[0] == Bytes("VRF"), vrf_function]
    )

    return program
