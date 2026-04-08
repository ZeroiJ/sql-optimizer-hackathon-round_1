from sql_optimizer_env.scripts.inference import main, log_start, log_step, log_end

if __name__ == "__main__":
    import asyncio
    from sql_optimizer_env.scripts.inference import main as _main

    asyncio.run(_main())
