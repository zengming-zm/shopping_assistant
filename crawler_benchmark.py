"""
Crawler Performance Benchmark
Compares single-threaded vs multi-threaded product crawling performance
"""

import time
import asyncio
from typing import Dict, Any

def benchmark_crawlers():
    """Run performance benchmark between crawlers"""
    
    test_sites = [
        "https://lucafaloni.com",
        # Add more test sites as needed
    ]
    
    print("🏁 Crawler Performance Benchmark")
    print("=" * 60)
    
    results = {}
    
    for site in test_sites:
        print(f"\n🌐 Testing site: {site}")
        print("-" * 40)
        
        site_results = {}
        
        # Test 1: Single-threaded crawler
        print("1️⃣ Single-threaded crawler...")
        try:
            from product_crawler import run_product_crawler
            
            start_time = time.time()
            single_products = run_product_crawler(site, None)  # No progress callback for cleaner output
            single_time = time.time() - start_time
            
            single_rate = len(single_products) / single_time if single_time > 0 else 0
            site_results['single'] = {
                'products': len(single_products),
                'time': single_time,
                'rate': single_rate
            }
            
            print(f"   ✅ {len(single_products)} products in {single_time:.2f}s ({single_rate:.2f}/s)")
            
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            site_results['single'] = None
        
        # Test 2: Multi-threaded crawler (2 workers)
        print("2️⃣ Multi-threaded crawler (2 workers)...")
        try:
            from multithreaded_product_crawler import run_multithreaded_product_crawler
            
            start_time = time.time()
            multi_products_2 = run_multithreaded_product_crawler(
                site, None, max_workers=2, max_urls=20
            )
            multi_time_2 = time.time() - start_time
            
            multi_rate_2 = len(multi_products_2) / multi_time_2 if multi_time_2 > 0 else 0
            site_results['multi_2'] = {
                'products': len(multi_products_2),
                'time': multi_time_2,
                'rate': multi_rate_2
            }
            
            print(f"   ✅ {len(multi_products_2)} products in {multi_time_2:.2f}s ({multi_rate_2:.2f}/s)")
            
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            site_results['multi_2'] = None
        
        # Test 3: Multi-threaded crawler (4 workers)
        print("3️⃣ Multi-threaded crawler (4 workers)...")
        try:
            start_time = time.time()
            multi_products_4 = run_multithreaded_product_crawler(
                site, None, max_workers=4, max_urls=20
            )
            multi_time_4 = time.time() - start_time
            
            multi_rate_4 = len(multi_products_4) / multi_time_4 if multi_time_4 > 0 else 0
            site_results['multi_4'] = {
                'products': len(multi_products_4),
                'time': multi_time_4,
                'rate': multi_rate_4
            }
            
            print(f"   ✅ {len(multi_products_4)} products in {multi_time_4:.2f}s ({multi_rate_4:.2f}/s)")
            
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            site_results['multi_4'] = None
        
        results[site] = site_results
        
        # Performance comparison for this site
        print("\n📊 Performance Summary:")
        if site_results.get('single') and site_results.get('multi_2') and site_results.get('multi_4'):
            single = site_results['single']
            multi_2 = site_results['multi_2']
            multi_4 = site_results['multi_4']
            
            speedup_2 = single['time'] / multi_2['time'] if multi_2['time'] > 0 else 0
            speedup_4 = single['time'] / multi_4['time'] if multi_4['time'] > 0 else 0
            
            print(f"   Single-threaded:  {single['time']:.2f}s ({single['rate']:.2f}/s)")
            print(f"   Multi (2 workers): {multi_2['time']:.2f}s ({multi_2['rate']:.2f}/s) - {speedup_2:.2f}x speedup")
            print(f"   Multi (4 workers): {multi_4['time']:.2f}s ({multi_4['rate']:.2f}/s) - {speedup_4:.2f}x speedup")
            
            best_performer = max(
                [('single', single), ('multi_2', multi_2), ('multi_4', multi_4)],
                key=lambda x: x[1]['rate']
            )
            print(f"   🏆 Best performer: {best_performer[0]} ({best_performer[1]['rate']:.2f}/s)")
    
    # Overall summary
    print("\n🎯 Overall Benchmark Results:")
    print("=" * 60)
    
    for site, site_results in results.items():
        print(f"\n{site}:")
        for method, data in site_results.items():
            if data:
                print(f"   {method}: {data['products']} products, {data['time']:.2f}s, {data['rate']:.2f}/s")
    
    print("\n✨ Benchmark complete!")

if __name__ == "__main__":
    benchmark_crawlers()