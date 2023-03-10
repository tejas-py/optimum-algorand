from pyteal import *
from beaker import *
from typing import Final


class Optimum(Application):

    #####################
    # Application States
    #####################
    ADMIN: Final[ApplicationStateValue] = ApplicationStateValue(
        stack_type=TealType.bytes, default=Txn.sender(), static=True,
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
        return Seq(
            self.initialize_account_state()
        )

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
            opt_asa_id
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
    def handle_withdraw(self, opt_asa_id: abi.Uint64, fee_addr: abi.String):
        optBalOfAppAcc = AssetHolding.balance(
            Global.current_application_address(),
            opt_asa_id
        )
        scratch_amount = ScratchVar(TealType.uint64)
        def saveAmount(amount): return scratch_amount.store(amount)
        def amount(): return scratch_amount.load()
        return Seq(
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
                Div(
                    Mul(
                        Gtxn[0].asset_amount(),
                        (Balance(Global.current_application_address()) + self.GLOBAL_CUSTODIAL_DEPOSIT.get()) - Int(int(10e5))
                    ),
                    (Int(int(10e15)) - (optBalOfAppAcc.value() - Gtxn[0].asset_amount()))
                ),
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
            If(self.LOCAL_OPT_AMOUNT[Txn.sender()].get() >= Gtxn[0].asset_amount())
            .Then(
                    self.LOCAL_OPT_AMOUNT[Txn.sender()].set(
                        self.LOCAL_OPT_AMOUNT[Txn.sender()].get() - Gtxn[0].asset_amount()
                    )
            )
        )

    @internal
    def get_randomness(self):
        return Seq(
            # Prep arguments
            (round_number := abi.Uint64()).set(Global.round() - Int(10)),
            (user_data := abi.make(abi.DynamicArray[abi.Byte])).set([]),
            InnerTxnBuilder.ExecuteMethodCall(
                app_id=Txn.applications[1],
                method_signature="must_get(uint64,byte[])byte[]",
                args=[round_number, user_data],
            ),
            # Extract the first 9 digits
            Extract(InnerTxn.last_log(), Int(0), Int(9))
        )

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
    def set_governance_timelines(self, global_reward_distribution: abi.Uint64, global_registration_end: abi.Uint64,
                                 period_start: abi.Uint64, period_end: abi.Uint64):
        app_balance = AssetHolding.balance(
            Global.current_application_address(), Txn.assets[0]
        )
        return Seq(
            app_balance,
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
                    self.GLOBAL_TOTAL_OPT_DISPERSED_AT_GOVERNANCE.set(
                        Minus(
                            Int(int(10e15)),  # 10 Billion
                            app_balance.value()
                        )
                    ),
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
                    self.GLOBAL_CUSTODIAL_DEPOSIT.set(self.GLOBAL_CUSTODIAL_DEPOSIT.get() - Int(int(10e9)))
                ])
            )
        )

    @external
    def opt_in_asa(self):
        app_balance = AssetHolding.balance(
            Global.current_application_address(), Txn.assets[0])
        return Seq(
            app_balance,
            Assert(
                And(
                    Global.group_size() == Int(1),
                    self.basic_checks(tx_idx=Int(0)),
                    app_balance.value() == Int(0)
                )
            ),
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.xfer_asset: Txn.assets[0],
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
            .Then(self.handle_deposit(opt_asa_id=opt_asset_index.get()))

            .ElseIf(Gtxn[0].type_enum() == TxnType.AssetTransfer)
            .Then(self.handle_withdraw(opt_asa_id=opt_asset_index.get(), fee_addr=arg_fee_address.get()))

            .Else(Err())
        )

    @external
    def register_custodial_wallets(self):
        i = ScratchVar(TealType.uint64)
        return Seq(
            Assert(
                And(
                    self.basic_checks(tx_idx=Txn.group_index()),
                    Global.latest_timestamp() <= self.GLOBAL_REGISTRATION_END.get(),
                    Txn.sender() == self.ADMIN.get()
                )
            ),
            # Now, for each txn.account of current transaction EXCEPT the last one (as it is the
            # governance address), register the wallet
            For(i.store(Int(1)), i.load() < Txn.accounts.length(), i.store(i.load() + Int(1))).Do(
                Seq([
                    # for each account, verify that it's whitelisted already & NOT registered
                    Assert(
                        And(
                            self.LOCAL_WHITELISTED[Txn.accounts[i.load()]].get() == Int(1),
                            # registered nonce should be less than "current" governance nonce, otherwise we have already registered
                            self.LOCAL_REGISTERED[Txn.accounts[i.load()]].get() < self.GLOBAL_GOVERNANCE_NONCE.get()
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
                    self.LOCAL_REGISTERED[Txn.accounts[i.load()]].set(self.GLOBAL_GOVERNANCE_NONCE.get()),
                ])
            )
        )

    @external
    def vote_by_custodial_wallets(self):
        i = ScratchVar(TealType.uint64)
        return Seq(
            Assert(
                And(
                    self.basic_checks(tx_idx=Txn.group_index()),
                    Txn.sender() == self.ADMIN.get()
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
                            self.LOCAL_WHITELISTED[Txn.accounts[i.load()]].get() == Int(1),
                            self.LOCAL_REGISTERED[Txn.accounts[i.load()]].get() == self.GLOBAL_GOVERNANCE_NONCE.get(),
                            self.LOCAL_VOTED[Txn.accounts[i.load()]].get() < self.GLOBAL_GOVERNANCE_NONCE.get()
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
                    self.LOCAL_VOTED[Txn.accounts[i.load()]].set(
                        self.GLOBAL_GOVERNANCE_NONCE.get()
                    )
                ])
            )
        )

    @external
    def custodial_withdraw_rewards(self):
        i = ScratchVar(TealType.uint64)
        return Seq(
            Assert(
                And(
                    self.basic_checks(tx_idx=Txn.group_index()),
                    Txn.sender() == self.ADMIN.get()
                )
            ),
            # Now, for each txn.account of current transaction, withraw rewards from it (after verification)
            For(i.store(Int(1)), i.load() <= Txn.accounts.length(), i.store(i.load() + Int(1))).Do(
                Seq([
                    # for each account, verify that it's whitelisted 10000 ALGO is deposited
                    Assert(
                        And(
                            self.LOCAL_WHITELISTED[Txn.accounts[i.load()]].get() == Int(1),
                            self.LOCAL_REGISTERED[Txn.accounts[i.load()]].get() == self.GLOBAL_GOVERNANCE_NONCE.get(),
                            self.LOCAL_VOTED[Txn.accounts[i.load()]].get() == self.GLOBAL_GOVERNANCE_NONCE.get(),

                            # Ensure that after withdrawing the reward amount from the custodial wallet
                            # 10000 ALGO + account_min_balance remains (which the user can withdraw later).
                            (Balance(Txn.accounts[i.load()]) - Btoi(Txn.application_args[i.load()])) >= Int(int(10e9))
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
            )
        )

    @external
    def custodial_close_wallets(self):
        i = ScratchVar(TealType.uint64)
        return Seq(
            Assert(
                self.basic_checks(tx_idx=Txn.group_index()),
                Txn.sender() == self.ADMIN.get()
            ),
            # Now, for each txn.account of current transaction, withraw rewards from it (after verification)
            For(i.store(Int(1)), i.load() <= Txn.accounts.length(), i.store(i.load() + Int(1))).Do(
                Seq([
                    # for each account, verify that it's whitelisted
                    Assert(self.LOCAL_WHITELISTED[Txn.accounts[i.load()]].get() == Int(1)),
                    # set up a tx with "rekey to" set as the admin (sender)
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
            )
        )

    @external
    def disperse_lottery(self, opt_asset_index: abi.Uint64, fee_addr: abi.String, reward_amount: abi.Uint64):
        return Seq(
            Assert(
                self.basic_checks(tx_idx=Txn.group_index()),
                Txn.sender() == self.ADMIN.get(),

                # ensure atleast 23h b/w consecutive lottery dispersals
                Global.latest_timestamp() - self.GLOBAL_LAST_LOTTERY_DISPERSAL_TS.get() >= Int(82800)
            ),

            # deposit reward amount to the winner address (90%)
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.xfer_asset: opt_asset_index.get(),
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
                    TxnField.xfer_asset: opt_asset_index.get(),
                    TxnField.asset_receiver: fee_addr.get(),
                    TxnField.asset_amount: Btoi(Txn.application_args[2]),
                    # fee is set externally
                    TxnField.fee: Int(0)
                }
            ),
            InnerTxnBuilder.Submit(),

            # track last time lottery was dispersed (to ensure gap b/w consecutive lottery is atleast 23h)
            self.GLOBAL_LAST_LOTTERY_DISPERSAL_TS.set(Global.latest_timestamp()),

            # update local state to track the winner and the lottery amt (to show in table in UI)
            self.LOCAL_OPT_REWARD_AMOUNT[Txn.accounts[1]].set(
                self.LOCAL_OPT_REWARD_AMOUNT.get() + reward_amount.get()
            ),

            # update local opt amount key deposited to user (i.e track deposits + lottery winnings for a user)
            self.LOCAL_OPT_AMOUNT[Txn.accounts[1]].set(
                self.LOCAL_OPT_AMOUNT[Txn.accounts[1]].get() + reward_amount.get()
            )
        )

    @external
    def VRF(self, *, output: abi.Uint64):
        return Seq(
            (randomness_number := abi.DynamicBytes()).decode(self.get_randomness()),
            output.set(Mod(Btoi(randomness_number.get()), Int(9999999)))
        )

    @clear_state()
    def clear_state(self):
        return Approve()


if __name__ == "__main__":

    Optimum().dump("./artifacts")


