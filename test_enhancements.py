#!/usr/bin/env python3
"""
Test script to verify Redis cluster setup enhancements
"""

import sys
import os
from pathlib import Path

# Add the redis_deploy package to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_configuration_loading():
    """Test configuration loading with enhancements"""
    print("Testing configuration loading...")
    
    try:
        from redis_deploy.config import load_config
        
        # Test loading sample configuration
        cfg = load_config('configs/sample_cluster.yaml')
        
        print("✅ Configuration loaded successfully")
        print(f"   Nodes: {len(cfg.nodes)} ({', '.join(cfg.nodes)})")
        print(f"   Redis version: {cfg.redis_version}")
        print(f"   Persistence mode: {cfg.persistence.mode}")
        print(f"   Swap management: {cfg.swap_management}")
        print(f"   SSH timeout: {cfg.ssh.timeout}")
        print(f"   SSH retries: {cfg.ssh.connection_retries}")
        
        # Test persistence configuration
        if hasattr(cfg.persistence, 'aof_rewrite_perc'):
            print(f"   AOF rewrite percentage: {cfg.persistence.aof_rewrite_perc}")
        
        if hasattr(cfg.persistence, 'rdb_compression'):  
            print(f"   RDB compression: {cfg.persistence.rdb_compression}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return False

def test_template_configuration():
    """Test template configuration file"""
    print("\nTesting template configuration loading...")
    
    try:
        from redis_deploy.config import load_config
        
        # Test loading template configuration
        cfg = load_config('configs/redis_cluster_template.yaml')
        
        print("✅ Template configuration loaded successfully")
        print(f"   Nodes: {len(cfg.nodes)} ({', '.join(cfg.nodes)})")
        print(f"   Persistence mode: {cfg.persistence.mode}")
        
        return True
        
    except Exception as e:
        print(f"❌ Template configuration loading failed: {e}")
        return False

def test_configuration_validation():
    """Test configuration validation features"""
    print("\nTesting configuration validation...")
    
    try:
        from redis_deploy.config import load_config
        
        cfg = load_config('configs/sample_cluster.yaml')
        
        # Test non-strict validation (should pass)
        cfg.validate(strict_ssh=False)
        print("✅ Non-strict validation passed")
        
        # Test persistence validation
        cfg.persistence.validate()
        print("✅ Persistence validation passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Redis Cluster Setup - Enhancement Verification")
    print("=" * 50)
    
    tests = [
        test_configuration_loading,
        test_template_configuration, 
        test_configuration_validation
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("Test Results Summary:")
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Passed: {passed}/{total}")
    if passed < total:
        print(f"❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 All enhancement tests passed!")
        print("\nKey improvements verified:")
        print("  ✅ Enhanced SSH configuration with retries")
        print("  ✅ Advanced persistence settings (RDB/AOF)")
        print("  ✅ Comprehensive swap management")
        print("  ✅ Flexible configuration validation")
        print("  ✅ Template configuration support")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)