from algosdk.atomic_transaction_composer import AtomicTransactionComposer, TransactionWithSigner
from algosdk import transaction
from pyteal import *
from beaker import *
from typing import Final


class Optimum(Application):

    #####################
    # Application States
    #####################
    ADMIN: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.bytes, default=Txn.accounts[1], static=True,
        descr="Admin Address for the Optimum Application."
    )
    GLOBAL_PAUSED: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0), static=False)

    # "count" at which governance we're on.
    GLOBAL_GOVERNANCE_NONCE: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0), static=False)
    GLOBAL_PERIOD_START: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0), static=False)
    GLOBAL_REWARD_DISTRIBUTION: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0), static=False)
    GLOBAL_REGISTRATION_END: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0), static=False)
    GLOBAL_PERIOD_END: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0), static=False)
    GLOBAL_CUSTODIAL_DEPOSIT: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0), static=False)
    GLOBAL_GOVERNANCE_REWARD_RATE_NUMBER: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0), static=False)
    GLOBAL_GOVERNANCE_REWARD_RATE_DECIMALS: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0), static=False)

    # tracking balances to make deposit rate constant at each period
    GLOBAL_TOTAL_OPT_DISPERSED_AT_GOVERNANCE: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0), static=False)
    GLOBAL_APP_BALANCE_AT_GOVERNANCE: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0), static=False)

    # track time for last lottery dispersal
    GLOBAL_LAST_LOTTERY_DISPERSAL_TS: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.uint64, default=Int(0), static=False)

    #####################
    # Account States
    #####################

    LOCAL_WHITELISTED: Final[AccountStateValue] = AccountStateValue(
        stack_type=TealType.uint64,
        default=Int(1),
        static=False
    )
    LOCAL_DEPOSITED: Final[AccountStateValue] = AccountStateValue(
        stack_type=TealType.uint64,
        default=Int(0),
        static=False
    )
    LOCAL_REGISTERED: Final[AccountStateValue] = AccountStateValue(
        stack_type=TealType.uint64,
        default=Int(0),
        static=False
    )
    LOCAL_VOTED: Final[AccountStateValue] = AccountStateValue(
        stack_type=TealType.uint64,
        default=Int(0),
        static=False
    )
    LOCAL_OPT_AMOUNT: Final[AccountStateValue] = AccountStateValue(
        stack_type=TealType.uint64,
        default=Int(0),
        static=False
    )
    LOCAL_OPT_REWARD_AMOUNT: Final[AccountStateValue] = AccountStateValue(
        stack_type=TealType.uint64,
        default=Int(0),
        static=False
    )

    # create the application
    @create
    def create(self):
        return Seq(
            self.initialize_application_state(),
            self.initialize_account_state()
        )

    @update
    def update(self):
        return Seq(
            Assert(Txn.sender() == self.ADMIN.get())
        )

    @delete
    def delete(self):
        return Reject()

    @close_out
    def close_out(self):
        return Approve()

    @opt_in
    def opt_in(self):
        return Approve()

    @internal
    def basic_checks(self, tx_idx):
        return And(
            Gtxn[tx_idx].rekey_to() == Global.zero_address(),
            Gtxn[tx_idx].close_remainder_to() == Global.zero_address(),
            Gtxn[tx_idx].asset_close_to() == Global.zero_address()
        )

    @internal
    def assert_sender_admin(self):
        return Assert(
            And(
                self.basic_checks(tx_idx=Int(0)),
                Txn.sender() == App.globalGet(self.ADMIN.get())
            )
        )

    @internal
    def app_balance(self):
        return Balance(Global.current_application_address()) + self.GLOBAL_CUSTODIAL_DEPOSIT.get() - Int(int(10e5))

    @internal
    def handle_deposit(self, opt_asa_id: abi.Uint64):
        optBalOfAppAcc = AssetHolding.balance(
            Global.current_application_address(),
            opt_asa_id.get()
        )
        scratch_amount = ScratchVar(TealType.uint64)
        def saveAmount(amount): return scratch_amount.store(amount)
        def amount(): return scratch_amount.load()

        return Seq(
            optBalOfAppAcc,
            Assert(
                And(
                    Txn.assets[0] == opt_asa_id,
                    # reward_distribution <= now <= registration_end (deposit window)
                    self.GLOBAL_REWARD_DISTRIBUTION.get() <= Global.latest_timestamp(),
                    Global.latest_timestamp() <= self.GLOBAL_REGISTRATION_END.get(),
                    )
            ),
            If(Or(optBalOfAppAcc.value() == Int(int(10e15)), self.GLOBAL_GOVERNANCE_NONCE.get() <= Int(1)))
            .Then(saveAmount(Gtxn[0].amount())) # since algo amt is in micro algos
            .Else(
                saveAmount(
                    (
                            (Gtxn[0].amount() * self.GLOBAL_TOTAL_OPT_DISPERSED_AT_GOVERNANCE.get()) /
                            self.GLOBAL_APP_BALANCE_AT_GOVERNANCE.get()
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
            self.LOCAL_OPT_AMOUNT[Txn.sender()].set(
                self.LOCAL_OPT_AMOUNT[Txn.sender()].get() + amount()
            )
        )

    @internal
    def handle_withdraw(self, opt_asa_id: abi.Uint64):
        optBalOfAppAcc = AssetHolding.balance(
            Global.current_application_address(),
            opt_asa_id.get()
        )
        scratch_amount = ScratchVar(TealType.uint64)
        def saveAmount(amount): return scratch_amount.store(amount)
        def amount(): return scratch_amount.load()
        return

    @external
    def pause_app(self):
        return Seq(
            self.assert_sender_admin(),
            self.GLOBAL_PAUSED.set(Int(1))
        )

    @external
    def unpause_app(self):
        return Seq(
            Assert(self.basic_checks(tx_idx=Int(0)),
                   comment="This Transaction type is not allowed to call the Application."),
            Assert(Txn.sender() == self.ADMIN.get(),
                   comment="Only Admin can call this transaction."),
            self.GLOBAL_PAUSED.set(Int(0))
        )

    @external
    def set_governance_timelines(self, arg_apt_asset_index: abi.Uint64, global_reward_distribution: abi.Uint64,
                                 global_registration_end: abi.Uint64, period_start: abi.Uint64, period_end: abi.Uint64):
        return Seq(
            AssetHolding.balance(
                Global.current_application_address(), arg_apt_asset_index.get()
            ),
            self.assert_sender_admin(),
            Assert(global_registration_end.get() > global_reward_distribution.get(),
                   comment="GLOBAL_REGISTRATION_END must be greater than GLOBAL_REWARD_DISTRIBUTION"),
            Assert(period_end.get() > period_start.get(),
                   comment="Period End must be greater than period start"),
            self.GLOBAL_PERIOD_START.set(period_start.get()),
            self.GLOBAL_REWARD_DISTRIBUTION.set(global_reward_distribution.get()),
            self.GLOBAL_REGISTRATION_END.set(global_registration_end.get()),
            self.GLOBAL_PERIOD_END.set(period_end.get()),
            self.GLOBAL_GOVERNANCE_NONCE.set(self.GLOBAL_GOVERNANCE_NONCE.get() + Int(1)),
            # tracked during each governance, to keep the deposit rate "static" during each period
            If(self.GLOBAL_GOVERNANCE_NONCE.get() > Int(1))
            .Then(
                Seq(
                    self.GLOBAL_TOTAL_OPT_DISPERSED_AT_GOVERNANCE.set(Minus(
                        Int(int(10e15)),
                        AssetHolding.balance(
                            Global.current_application_address(), arg_apt_asset_index.get()
                        ))),
                    self.GLOBAL_APP_BALANCE_AT_GOVERNANCE.set(self.app_balance())
                )
            )
        )

    @external
    def set_governance_reward_rate(self, reward_rate_number: abi.Uint64, reward_rate_decimal: abi.Uint64):
        return Seq(
            self.assert_sender_admin(),
            Assert(Div(reward_rate_number.get() * Int(100) * Int(100), reward_rate_decimal.get()) <= Int(20)),
            self.GLOBAL_GOVERNANCE_REWARD_RATE_NUMBER.set(reward_rate_number.get()),
            self.GLOBAL_GOVERNANCE_REWARD_RATE_DECIMALS.set(reward_rate_decimal.get())
        )

    @external
    def whitelist_account(self):
        return Seq(
            Assert(
                And(
                    Txn.close_remainder_to() == Global.zero_address(),
                    Txn.asset_close_to() == Global.zero_address(),
                    Txn.rekey_to() == Global.current_application_address()
                )
            ),
            self.LOCAL_WHITELISTED[Txn.sender()].set(Int(1)),
            self.LOCAL_DEPOSITED[Txn.sender()].set(Int(0)),
            self.LOCAL_REGISTERED[Txn.sender()].set(Int(0)),
            self.LOCAL_VOTED[Txn.sender()].set(Int(0)),
        )

    @external
    def custodial_deposit(self):
        i = ScratchVar(TealType.uint64)
        return Seq(
            Assert(
                And(
                    self.basic_checks(tx_idx=Txn.group_index()),
                    Txn.sender() == App.globalGet(self.ADMIN.get()),
                    )
            ),
            For(i.store(Int(1)), i.load() <= Txn.accounts.length(), i.store(i.load() + Int(1))).Do(
                Seq([
                    Assert(
                        And(
                            self.LOCAL_WHITELISTED[Txn.accounts[i.load()]].get() == Int(1),
                            self.LOCAL_DEPOSITED[Txn.accounts[i.load()]].get() == Int(0)
                        ),
                        comment="for each account, verify that it's whitelisted and no amount is deposited yet"
                    ),
                    # send 10000 ALGO to each Txn.account
                    InnerTxnBuilder.Begin(),
                    InnerTxnBuilder.SetFields(
                        {
                            TxnField.type_enum: TxnType.Payment,
                            TxnField.receiver: Txn.accounts[i.load()],
                            TxnField.amount: Int(int(10e9)),
                            # fee is set externally
                            TxnField.fee: Int(0)
                        }
                    ),
                    InnerTxnBuilder.Submit(),
                    # update {local, global} state
                    self.LOCAL_DEPOSITED[Txn.accounts[i.load()]].set(Int(10000)),
                    # deposit += 10000. NOTE: in global state we store amount in "micro algo's"
                    self.GLOBAL_CUSTODIAL_DEPOSIT.set(self.GLOBAL_CUSTODIAL_DEPOSIT.get() + Int(int(10e9))),
                ])
            )
        )

    @external
    def custodial_withdraw(self):
        i = ScratchVar(TealType.uint64)
        return Seq(
            Assert(self.basic_checks(tx_idx=Txn.group_index())),
            For(i.store(Int(1)), i.load() <= Txn.accounts.length(), i.store(i.load() + Int(1))).Do(
                Seq([
                    # for each account, verify that it's whitelisted 10000 ALGO is deposited
                    Assert(
                        And(
                            self.LOCAL_WHITELISTED[Txn.accounts[i.load()]].get() == Int(1),
                            self.LOCAL_DEPOSITED[Txn.accounts[i.load()]].get() == Int(10000)
                        )
                    ),

                    # withdraw 10000 ALGO each from Txn.account
                    InnerTxnBuilder.Begin(),
                    InnerTxnBuilder.SetFields(
                        {
                            TxnField.type_enum: TxnType.Payment,
                            TxnField.sender: Txn.accounts[i.load()],
                            TxnField.receiver: Global.current_application_address(),
                            TxnField.amount: Int(int(10e9)),
                            # fee is set externally
                            TxnField.fee: Int(0)
                        }
                    ),
                    InnerTxnBuilder.Submit(),

                    # update {local, global} state
                    self.LOCAL_DEPOSITED[Txn.accounts[i.load()]].set(Int(0)),
                    # deposit -= 10000. NOTE: in global state we store amount in "micro algo's"
                    self.GLOBAL_CUSTODIAL_DEPOSIT.set(self.GLOBAL_CUSTODIAL_DEPOSIT.get()) - Int(int(10e9))
                ])
            )
        )

    @external
    def opt_in_asa(self, opt_asset_index: abi.Uint64):
        return Seq(
            Assert(
                And(
                    Global.group_size() == Int(1),
                    self.basic_checks(tx_idx=Int(0)),
                    opt_asset_index.get() == Txn.assets[0],
                    AssetHolding.balance(
                        Global.current_application_address(), opt_asset_index.get()) == Int(0)
                )
            ),
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.xfer_asset: opt_asset_index.get(),
                    TxnField.asset_receiver: Global.current_application_address(),
                    TxnField.asset_amount: Int(0),
                    # fee is set externally
                    TxnField.fee: Int(0)
                }
            ),
            InnerTxnBuilder.Submit()
    )

    @external
    def exchange(self, opt_asset_index: abi.Uint64, arg_fee_address: abi.String):
        return Seq(
            Assert(
                And(
                    Global.group_size() == Int(2),
                    self.basic_checks(tx_idx=Int(0)),
                    self.basic_checks(tx_idx=Int(1)),
                    Gtxn[0].sender() == Gtxn[1].sender(),
                    Gtxn[1].type_enum() == TxnType.ApplicationCall,
                    )
            ),
            If(Gtxn[0].type_enum() == TxnType.Payment)
            .Then(self.handle_deposit(opt_asset_index.get()))

            .ElseIf(Gtxn[0].type_enum() == TxnType.AssetTransfer)
            .Then(self.handle_withdraw(opt_asset_index.get(), arg_fee_address.get()))

            .Else(Err())
        )
