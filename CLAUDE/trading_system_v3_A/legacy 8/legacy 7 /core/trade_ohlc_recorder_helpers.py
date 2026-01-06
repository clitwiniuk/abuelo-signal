    def get_existing_snapshot(self, symbol: str, trading_date: str) -> Optional[TradeOHLCSnapshot]:
        """Buscar si ya existe un snapshot para este símbolo/día en la DB"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                # Buscamos por símbolo y fecha, ordenado por creado (el último)
                row = conn.execute("""
                    SELECT * FROM trade_ohlc_snapshots 
                    WHERE symbol = ? AND trading_date = ? 
                    ORDER BY created_at DESC LIMIT 1
                """, (symbol, trading_date)).fetchone()
                
                if not row:
                    return None
                    
                # Reconstruir objeto Snapshot desde DB
                return TradeOHLCSnapshot(
                    trade_id=row['trade_id'],
                    symbol=row['symbol'],
                    trading_date=row['trading_date'],
                    day_open=row['day_open'],
                    day_high=row['day_high'],
                    day_low=row['day_low'],
                    day_close=row['day_close'],
                    day_volume=row['day_volume'],
                    entry_time=datetime.fromisoformat(row['entry_time']) if isinstance(row['entry_time'], str) else row['entry_time'],
                    entry_price=row['entry_price'],
                    entry_bar=json.loads(row['entry_bar']) if row['entry_bar'] else None,
                    exit_time=datetime.fromisoformat(row['exit_time']) if row['exit_time'] else None,
                    exit_price=row['exit_price'],
                    exit_bar=json.loads(row['exit_bar']) if row['exit_bar'] else None,
                    premarket_high=row['premarket_high'],
                    gap_percent=row['gap_percent'],
                    market_open_price=row['market_open_price'],
                    intraday_bars=row['intraday_bars']
                )
        except Exception as e:
            self.logger.error(f"❌ Error checking existing snapshot: {e}")
            return None

    def save_all_active_snapshots(self):
        """Guardar todos los snapshots activos en DB (para Shutdown/Safety)"""
        with self._lock:
            count = 0
            for trade_id, snapshot in self._active_trades.items():
                try:
                    # Actualizar con últimas barras disponibles
                    symbol = snapshot.symbol
                    trading_date = snapshot.trading_date
                    daily_bars = self._daily_data_cache.get(symbol, {}).get(trading_date, [])
                    
                    if daily_bars:
                        snapshot.day_high = max(snapshot.day_high, max(bar.high for bar in daily_bars))
                        snapshot.day_low = min(snapshot.day_low, min(bar.low for bar in daily_bars))
                        snapshot.day_close = daily_bars[-1].close
                        snapshot.day_volume = sum(bar.volume for bar in daily_bars)
                        snapshot.intraday_bars = json.dumps([self._bar_to_dict(bar) for bar in daily_bars])
                    
                    self._save_snapshot_to_db(snapshot)
                    count += 1
                except Exception as e:
                    self.logger.error(f"❌ Error saving snapshot for {trade_id} during cleanup: {e}")
            
            if count > 0:
                self.logger.info(f"💾 Safety Save: Persisted {count} active trade snapshots to DB.")
