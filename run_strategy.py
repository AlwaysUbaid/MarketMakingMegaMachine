#!/usr/bin/env python3

import os
import sys
import json
import logging
import argparse
import time

def main():
    """Entry point for running a specific strategy"""
    parser = argparse.ArgumentParser(description='Run a MMMM Trading Strategy')
    parser.add_argument('strategy', type=str, help='Name of the strategy to run')
    parser.add_argument('-t', '--testnet', action='store_true', help='Use testnet instead of mainnet')
    parser.add_argument('-p', '--params', type=str, help='JSON string or file path with strategy parameters')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--log-file', type=str, help='Path to log file')
    
    args = parser.parse_args()
    
    # Process parameters if provided
    params_str = None
    if args.params:
        # Check if it's a file path
        if os.path.isfile(args.params):
            with open(args.params, 'r') as f:
                params_str = f.read()
        else:
            # Assume it's a JSON string
            params_str = args.params
    
    # Build command for main.py
    cmd_parts = [sys.executable, 'main.py', '-s', args.strategy]
    
    if args.testnet:
        cmd_parts.append('-t')
    
    if args.verbose:
        cmd_parts.append('-v')
    
    if args.log_file:
        cmd_parts.extend(['--log-file', args.log_file])
    
    if params_str:
        cmd_parts.extend(['-p', params_str])
    
    # Execute main.py with the appropriate arguments
    cmd = ' '.join(cmd_parts)
    print(f"Executing: {cmd}")
    os.system(cmd)

if __name__ == '__main__':
    main()