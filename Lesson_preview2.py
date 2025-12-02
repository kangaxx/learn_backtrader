# 本例子用于展示通过tushare接口获取螺纹钢期货主力期货指数历史数据，并用Backtrader进行简单的回测。回测的策略是基于5日均线和20日均线的交叉策略。
import tushare as ts
import backtrader as bt
import pandas as pd
import json
import datetime
import matplotlib.pyplot as plt
import platform
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

# 加载tushare token
def load_tushare_token(token_file='Data/tushare_token.json'):
    try:
        # 读取文件内容并移除注释行
        with open(token_file, 'r', encoding='utf-8') as f:
            lines = [line for line in f if not line.strip().startswith('//')]
            content = ''.join(lines)
            token_data = json.loads(content)
            # 使用正确的字段名
            return token_data.get('tushare_token', '')
    except Exception as e:
        print(f"加载token文件失败: {e}")
        return ''

# 设置tushare token
token = load_tushare_token()
if token:
    try:
        ts.set_token(token)
        pro = ts.pro_api()
        print("Tushare API初始化成功")
    except Exception as e:
        print(f"Tushare API初始化失败: {e}")
        # 即使初始化失败，我们仍然可以尝试使用本地CSV文件
        pro = None
else:
    print("未找到有效的tushare token，将尝试使用本地CSV文件数据")
    pro = None

# 从tushare获取螺纹钢期货主力期货指数数据，失败时尝试使用本地CSV文件
def get_rb_index_data(start_date='20200101', end_date=None):
    # 首先尝试从tushare获取数据
    try:
        if end_date is None:
            end_date = datetime.datetime.now().strftime('%Y%m%d')
        
        # 螺纹钢期货主力期货指数的代码为RB.SHF
        df = pro.fut_daily(
            ts_code='RB.SHF',
            start_date=start_date,
            end_date=end_date
        )
        
        # 数据处理
        if not df.empty:
            # 重命名列以便Backtrader使用
            df = df.rename(columns={
                'trade_date': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'vol': 'volume'
            })
            
            # 处理日期格式
            # 尝试将日期字符串解析为YYYYMMDD格式
            try:
                # 检查第一个日期值是否为8位数字格式
                first_date = str(df['date'].iloc[0])
                if len(first_date) == 8 and first_date.isdigit():
                    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
                else:
                    # 尝试自动解析其他格式
                    df['date'] = pd.to_datetime(df['date'])
            except:
                # 如果解析失败，使用自动解析
                df['date'] = pd.to_datetime(df['date'])
            
            # 按照日期排序
            df = df.sort_values('date')
            
            # 设置索引
            df.set_index('date', inplace=True)
            
            print("成功从tushare获取数据")
            return df
    except Exception as e:
        print(f"从tushare获取数据失败: {e}")
    
    # 如果tushare获取失败，尝试使用本地CSV文件
    print("尝试使用本地CSV文件数据...")
    try:
        # 尝试读取Data目录下的RB9999.csv文件
        csv_file = 'Data/RB9999.csv'
        df = pd.read_csv(csv_file)
        
        if df.empty:
            print("本地CSV文件为空")
            return None
        
        # 根据常见的CSV格式进行处理
        # 假设CSV文件的列名可能是以下几种格式之一
        if 'date' in df.columns:
            date_col = 'date'
        elif 'trade_date' in df.columns:
            date_col = 'trade_date'
        elif 'datetime' in df.columns:
            date_col = 'datetime'
        elif '时间' in df.columns:
            date_col = '时间'
        else:
            # 默认使用第一列作为日期列
            date_col = df.columns[0]
        
        # 重命名必要的列
        column_mapping = {}
        for old_col, new_col in [
            (date_col, 'date'),
            ('open', 'open'), ('开盘价', 'open'), ('开盘', 'open'),
            ('high', 'high'), ('最高价', 'high'),
            ('low', 'low'), ('最低价', 'low'),
            ('close', 'close'), ('收盘价', 'close'), ('收盘', 'close'),
            ('volume', 'volume'), ('成交量', 'volume'), ('vol', 'volume')
        ]:
            if old_col in df.columns:
                column_mapping[old_col] = new_col
        
        df = df.rename(columns=column_mapping)
        
        # 确保必要的列存在
        required_cols = ['date', 'open', 'high', 'low', 'close']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"本地CSV文件缺少必要的列: {missing_cols}")
            return None
        
        # 特别处理trade_date列，确保使用正确的日期格式解析YYYYMMDD
        if 'date' in df.columns and len(df) > 0:
            # 尝试将日期字符串解析为YYYYMMDD格式
            try:
                # 检查第一个日期值是否为8位数字格式
                first_date = str(df['date'].iloc[0])
                if len(first_date) == 8 and first_date.isdigit():
                    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
                else:
                    # 尝试自动解析其他格式
                    df['date'] = pd.to_datetime(df['date'])
            except:
                # 如果解析失败，使用自动解析
                df['date'] = pd.to_datetime(df['date'])
        
        # 如果没有volume列，添加一个默认值
        if 'volume' not in df.columns:
            df['volume'] = 0
        
        # 按照日期排序
        df = df.sort_values('date')
        
        # 设置索引
        df.set_index('date', inplace=True)
        
        # 应用日期筛选
        if end_date is None:
            end_date_dt = datetime.datetime.now()
        else:
            # 将字符串格式的end_date转换为datetime
            end_date_dt = pd.to_datetime(end_date, format='%Y%m%d')
        
        # 将字符串格式的start_date转换为datetime
        start_date_dt = pd.to_datetime(start_date, format='%Y%m%d')
        
        # 筛选日期范围内的数据
        df = df.loc[start_date_dt:end_date_dt]
        
        print(f"成功从本地CSV文件获取数据，共{len(df)}条记录，日期范围: {start_date} 至 {end_date or '当前'}")
        return df
    except Exception as e:
        print(f"读取本地CSV文件失败: {e}")
        return None

# 定义策略类
class SmaCrossStrategy(bt.Strategy):
    params = (
        ('sma1', 5),    # 短期均线周期
        ('sma2', 20),   # 长期均线周期
        ('take_profit_pct', 0.03),  # 初始止盈百分比 (3%)
        ('trailing_profit_pct', 0.01),  # 移动止盈百分比 (1%)
    )
    
    def __init__(self):
        # 初始化日志
        self.log = self._log
        
        # 跟踪订单和持仓信息
        self.order = None
        self.entry_price = None  # 入场价格
        self.take_profit_price = None  # 当前止盈价格
        self.max_price = None  # 入场后的最高价
        
        # 创建两个移动平均线指标
        self.sma1 = bt.indicators.SimpleMovingAverage(
            self.datas[0].close, period=self.params.sma1
        )
        self.sma2 = bt.indicators.SimpleMovingAverage(
            self.datas[0].close, period=self.params.sma2
        )
        
        # 交叉信号
        self.crossover = bt.indicators.CrossOver(self.sma1, self.sma2)
    
    def update_trailing_profit(self):
        """更新动态止盈价格"""
        if not self.position:
            return
            
        current_high = self.datas[0].high[0]
        current_close = self.datas[0].close[0]
        
        # 更新入场后的最高价
        if self.max_price is None or current_high > self.max_price:
            self.max_price = current_high
            
            # 只有当价格已经达到或超过初始止盈价时，才更新移动止盈价格
            if self.max_price >= self.entry_price * (1 + self.params.take_profit_pct):
                new_take_profit = self.max_price * (1 - self.params.trailing_profit_pct)
                if new_take_profit > self.take_profit_price:
                    self.take_profit_price = new_take_profit
                    # 记录第一次达到止盈的标志
                    if not hasattr(self, 'profit_triggered'):
                        self.profit_triggered = True
                    # 打印止盈更新信息（可选）
                    # self.log(f"移动止盈更新: 最高价={self.max_price:.2f}, 止盈价={self.take_profit_price:.2f}")
    
    def check_take_profit(self):
        """检查是否达到止盈条件"""
        if not self.position or self.take_profit_price is None:
            return False
            
        # 只有当价格已经触发过止盈条件（达到或超过初始止盈价）后，才考虑回落卖出
        if not hasattr(self, 'profit_triggered'):
            # 检查是否首次达到初始止盈价
            if (self.datas[0].high[0] >= self.take_profit_price or 
                self.datas[0].close[0] >= self.take_profit_price):
                self.profit_triggered = True
                self.log(f"触发初始止盈: 当前价={self.datas[0].close[0]:.2f}, 止盈价={self.take_profit_price:.2f}")
                # 首次达到止盈价时不卖出，继续持有以跟踪更大利润
                return False
            return False
        
        # 已经触发过止盈，当价格回落到止盈价以下时卖出
        current_close = self.datas[0].close[0]
        current_low = self.datas[0].low[0]
        
        if current_close <= self.take_profit_price or current_low <= self.take_profit_price:
            return True
        return False
    
    def _log(self, txt, dt=None):
        """记录策略日志"""
        # 获取当前日期，确保格式正确
        if dt is None:
            try:
                dt = self.datas[0].datetime.date(0)
                # 检查日期是否为1970年（可能是解析错误）
                if dt.year == 1970:
                    # 使用回测中的索引位置作为替代标识
                    dt = f"Bar#{len(self)}"
            except:
                dt = f"Bar#{len(self)}"
        
        # 获取当前Bar的四个价格
        try:
            open_price = self.datas[0].open[0]
            high_price = self.datas[0].high[0]
            low_price = self.datas[0].low[0]
            close_price = self.datas[0].close[0]
            price_info = f"O={open_price:.2f}, H={high_price:.2f}, L={low_price:.2f}, C={close_price:.2f}"
        except:
            price_info = "价格信息不可用"
            
        print(f'{dt}, {price_info}, {txt}')
    
    def notify_order(self, order):
        """订单通知"""
        if order.status in [order.Submitted, order.Accepted]:
            # 订单已经提交或接受，不需要处理
            return
        
        # 获取当前的bar索引作为标识
        bar_id = f"Bar#{len(self)}"
        
        # 检查订单是否已完成
        if order.status in [order.Completed]:
            # 对于买入订单，记录入场价格和初始化止盈
            if order.isbuy():
                self.trade_entry_bar = len(self)
                self.entry_price = order.executed.price
                # 设置初始止盈价格
                self.take_profit_price = self.entry_price * (1 + self.params.take_profit_pct)
                self.max_price = self.entry_price
                # 重置止盈触发标志
                if hasattr(self, 'profit_triggered'):
                    delattr(self, 'profit_triggered')
                self.log(f'买入: 成交价={order.executed.price:.2f}, 成本={order.executed.value:.2f}, 佣金={order.executed.comm:.2f}')
                self.log(f'初始止盈: {self.take_profit_price:.2f} (上涨{self.params.take_profit_pct*100:.1f}%)')
            elif order.issell():
                # 检查是否为当日平仓（通过比较bar索引差值）
                is_same_day_close = hasattr(self, 'trade_entry_bar') and (len(self) - self.trade_entry_bar) <= 1
                # 重置止盈相关变量
                self.entry_price = None
                self.take_profit_price = None
                self.max_price = None
                if hasattr(self, 'profit_triggered'):
                    delattr(self, 'profit_triggered')
                self.log(f'卖出: 成交价={order.executed.price:.2f}, 收入={order.executed.value:.2f}, 佣金={order.executed.comm:.2f}, 当日平仓={is_same_day_close}')
            
            # 记录订单完成的时间
            self.bar_executed = len(self)
        
        # 如果订单被取消、拒绝或保证金不足
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单被取消/拒绝/保证金不足')
            # 重置止盈相关变量
            self.entry_price = None
            self.take_profit_price = None
            self.max_price = None
            if hasattr(self, 'profit_triggered'):
                delattr(self, 'profit_triggered')
        
        # 重置订单
        self.order = None
    
    def notify_trade(self, trade):
        """交易通知"""
        if not trade.isclosed:
            return
        
        # 使用bar索引来判断是否为当日平仓（在日线数据中，当日内交易通常发生在相邻的bar）
        is_same_day_trade = False
        if hasattr(self, 'trade_entry_bar'):
            bar_diff = len(self) - self.trade_entry_bar
            is_same_day_trade = bar_diff <= 1
        
        # 计算实际的交易佣金
        actual_commission = 6.2  # 默认佣金为6.2元（仅买入费用）
        if is_same_day_trade:
            actual_commission = 12.4  # 当日平仓收取买入和卖出各6.2元
        
        # 计算调整后的净利润
        adjusted_pnlcomm = trade.pnl - actual_commission
        
        # 输出交易信息，使用清晰的格式
        trade_type = "当日平仓" if is_same_day_trade else "非当日平仓"
        print(f"{'='*60}")
        # 获取交易结束日期
        try:
            end_date = self.datas[0].datetime.date(0)
            print(f"交易完成 - {trade_type} (日期: {end_date})")
        except:
            print(f"交易完成 - {trade_type} (Bar: {len(self)})")
        
        # 获取当前Bar的四个价格
        try:
            open_price = self.datas[0].open[0]
            high_price = self.datas[0].high[0]
            low_price = self.datas[0].low[0]
            close_price = self.datas[0].close[0]
            print(f"Bar: {len(self)}, 价格: O={open_price:.2f}, H={high_price:.2f}, L={low_price:.2f}, C={close_price:.2f}")
        except:
            print(f"Bar: {len(self)}, 价格信息不可用")
            
        print(f"毛利润: {trade.pnl:.2f}")
        print(f"佣金: {actual_commission:.2f}")
        print(f"净利润: {adjusted_pnlcomm:.2f}")
        print(f"{'='*60}")
        
        # 重置入场标识
        if hasattr(self, 'trade_entry_bar'):
            delattr(self, 'trade_entry_bar')
    
    def next(self):
        """策略核心逻辑"""
        # 如果有未完成的订单，不执行新的交易
        if self.order:
            return
        
        # 获取当前bar索引作为标识
        bar_id = f"Bar#{len(self)}"
        
        # 获取当前日期
        try:
            dt = self.datas[0].datetime.date(0)
            if dt.year == 1970:
                dt = f"Bar#{len(self)}"
        except:
            dt = f"Bar#{len(self)}"
        
        # 检查当前是否持仓
        if not self.position:
            # 没有持仓，检查是否有买入信号（短期均线上穿长期均线）
            if self.crossover > 0:
                # 获取当前Bar的四个价格
                open_price = self.datas[0].open[0]
                high_price = self.datas[0].high[0]
                low_price = self.datas[0].low[0]
                close_price = self.datas[0].close[0]
                
                print(f"\n{bar_id} - 买入信号")
                print(f"日期: {dt}, 价格: O={open_price:.2f}, H={high_price:.2f}, L={low_price:.2f}, C={close_price:.2f}")
                print(f"SMA{self.params.sma1}: {self.sma1[0]:.2f} > SMA{self.params.sma2}: {self.sma2[0]:.2f} (上穿)")
                # 买入
                self.order = self.buy()
        else:
            # 有持仓，先更新动态止盈
            self.update_trailing_profit()
            
            # 检查是否达到止盈条件
            if self.check_take_profit():
                # 获取当前Bar的四个价格
                open_price = self.datas[0].open[0]
                high_price = self.datas[0].high[0]
                low_price = self.datas[0].low[0]
                close_price = self.datas[0].close[0]
                
                print(f"\n{bar_id} - 止盈信号")
                print(f"日期: {dt}, 价格: O={open_price:.2f}, H={high_price:.2f}, L={low_price:.2f}, C={close_price:.2f}")
                print(f"当前价={close_price:.2f}, 跌破止盈价={self.take_profit_price:.2f}")
                # 止盈卖出
                self.order = self.sell()
            # 检查是否有卖出信号（短期均线下穿长期均线）
            elif self.crossover < 0:
                # 获取当前Bar的四个价格
                open_price = self.datas[0].open[0]
                high_price = self.datas[0].high[0]
                low_price = self.datas[0].low[0]
                close_price = self.datas[0].close[0]
                
                print(f"\n{bar_id} - 卖出信号")
                print(f"日期: {dt}, 价格: O={open_price:.2f}, H={high_price:.2f}, L={low_price:.2f}, C={close_price:.2f}")
                print(f"SMA{self.params.sma1}: {self.sma1[0]:.2f} < SMA{self.params.sma2}: {self.sma2[0]:.2f} (下穿)")
                # 卖出
                self.order = self.sell()

# 主函数
def main():
    # 获取数据
    print("正在获取螺纹钢期货主连数据...")
    df = get_rb_index_data(start_date='20200101')
    
    if df is None or df.empty:
        print("没有可用数据，无法进行回测")
        return
    
    print(f"获取到 {len(df)} 条数据记录")
    print("数据样例:")
    print(df.head())
    
    # 创建Backtrader数据馈送
    data = bt.feeds.PandasData(dataname=df)
    
    # 创建cerebro引擎
    cerebro = bt.Cerebro()
    
    # 添加数据
    cerebro.adddata(data)
    
    # 添加策略
    cerebro.addstrategy(SmaCrossStrategy)
    
    # 设置初始资金
    cerebro.broker.setcash(100000.0)
    
    # 设置自定义佣金：每手买入6.2元，当日平仓6.2元，非当日平仓免费
    # 保证金计算：价格 * 10 * 0.17
    class CommInfoFutures(bt.CommInfoBase):
        params = (
            ('stocklike', False),  # 期货模式
            ('commtype', bt.CommInfoBase.COMM_FIXED),  # 固定佣金
            ('commission', 6.2),  # 基础佣金（买入和当日平仓）
            ('mult', 10),  # 合约乘数
            ('margin', 0.17),  # 保证金率
        )
        
        def _getcommission(self, size, price, pseudoexec):
            # 买入订单总是收费6.2元/手
            if size > 0:
                return 6.2  # 买入收费
            # 卖出订单先按6.2元/手收费，后续在notify_order中会根据是否为当日平仓调整
            elif size < 0:
                return 6.2  # 卖出暂时收费，后续会在策略中调整
        
        def getsizing(self, price, cash, data=None):
            # 计算可买入的合约数量，基于可用现金和保证金要求
            # 保证金 = 价格 * 合约乘数 * 保证金率 = 价格 * 10 * 0.17
            margin_per_contract = price * self.params.mult * self.params.margin
            if margin_per_contract == 0:
                return 0
            # 确保有足够的现金支付保证金和佣金
            available_cash = cash - 6.2  # 预留佣金
            contracts = int(available_cash / margin_per_contract)
            return contracts
    
    # 创建佣金对象并设置到broker
    comminfo = CommInfoFutures()
    cerebro.broker.addcommissioninfo(comminfo)
    
    # 添加性能分析指标
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    # 打印初始资金
    print(f'初始资金: {cerebro.broker.getvalue():.2f}')
    
    # 运行回测
    print("正在运行回测...")
    results = cerebro.run()
    strategy = results[0]
    
    # 打印最终资金
    print(f'最终资金: {cerebro.broker.getvalue():.2f}')
    
    # 打印性能指标
    print("\n" + "="*60)
    print("性能指标")
    print("="*60)
    
    try:
        returns = strategy.analyzers.returns.get_analysis()
        print(f"总回报率: {returns['rtot']*100:.2f}%")
        print(f"年化回报率: {returns['rnorm100']:.2f}%")
    except Exception as e:
        print(f"计算回报率时出错: {e}")
    
    try:
        sharpe = strategy.analyzers.sharpe.get_analysis()
        print(f"夏普比率: {sharpe['sharperatio']:.2f}")
    except:
        print("无法计算夏普比率")
    
    try:
        drawdown = strategy.analyzers.drawdown.get_analysis()
        print(f"最大回撤: {drawdown['max']['drawdown']:.2f}%")
        print(f"最大回撤持续时间: {drawdown['max']['len']} 个交易日")
    except Exception as e:
        print(f"计算回撤时出错: {e}")
    
    try:
        trades = strategy.analyzers.trades.get_analysis()
        if 'total' in trades and 'closed' in trades['total']:
            print(f"交易次数: {trades['total']['closed']}")
            if 'won' in trades and 'total' in trades['won']:
                win_rate = trades['won']['total'] / trades['total']['closed'] * 100 if trades['total']['closed'] > 0 else 0
                print(f"胜率: {win_rate:.2f}%")
    except Exception as e:
        print(f"统计交易时出错: {e}")
    
    print("="*60)
    
    # 根据操作系统决定是否绘制回测结果
    current_os = platform.system().lower()
    if 'linux' in current_os:
        print("\n当前系统为Linux，跳过绘图步骤以避免显示问题")
    else:
        print("\n绘制回测结果...")
        try:
            cerebro.plot(style='line', figsize=(12, 8))
        except Exception as e:
            print(f"绘图时出现错误: {e}")
            print("跳过绘图步骤，但回测数据已计算完成")

if __name__ == '__main__':
    main()