import React from 'react';

export const Header: React.FC = () => {
    const toggleTheme = () => {
        if (document.documentElement.classList.contains('dark')) {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('theme', 'light');
        } else {
            document.documentElement.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        }
    };

    return (
        <header className="flex items-center justify-between whitespace-nowrap border-b border-solid border-gray-200 dark:border-gray-800 bg-white dark:bg-background-dark px-4 sm:px-6 md:px-10 py-3 sticky top-0 z-20">
            <div className="flex items-center gap-6">
                <div className="flex items-center gap-3 text-[#111418] dark:text-white">
                    <div className="size-6 text-primary">
                        <svg fill="none" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                            <path clipRule="evenodd" d="M24 4H6V17.3333V30.6667H24V44H42V30.6667V17.3333H24V4Z" fill="currentColor" fillRule="evenodd"></path>
                        </svg>
                    </div>
                    <h2 className="text-lg font-bold leading-tight tracking-[-0.015em]">BrokerDash</h2>
                </div>
                {/* Navigation links can be added here */}
            </div>
            <div className="flex items-center gap-2 sm:gap-4">
                <button
                    className="flex max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-full h-10 w-10 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                    onClick={toggleTheme}
                >
                    <span className="material-symbols-outlined text-xl dark:hidden">light_mode</span>
                    <span className="material-symbols-outlined text-xl hidden dark:inline">dark_mode</span>
                </button>
                {/* Profile dropdown can be added here */}
            </div>
        </header>
    );
};
