// include files for finding
#include "file.h"
#include "another.h"

// some similar tokens to test parsing single token
#define SOME_TOKEN_222
#define SOME_TOKEN

namespace scope
{
	struct hello
	{
		int world;
	};
	
	[[attributes]]
	struct second
	{
		[[attributes]]
		float x = 10;
		char array[100] = {};
		void function(int a, int b);
		void const_function(int c, int d) const;
		void inline_impl()
		{
			// ..
		}
	};

	enum test
	{
		one,
		two,
		three,
		four
	};
	
	enum test2
	{
		flag1 = 1<<0,
		flag2 = 1<<1,
		flag3 = 1<<2,
		flag4 = 1<<3
	};
}

// these kind of enums are nice, with scope
namespace e_enum_wrapped
{
	enum enum_wrapped
	{
		hello,
		world
	};
}
typedef e_enum_wrapped::enum_wrapped EnumWrapped;

void function_body()
{
	// comments with key words struct, enum, class
	
	/*
	multiline with struct definition
	
	struct test
	{
		int a = 0;
	}
	
	*/
	
	int a = 0;
	int b = a++;
	int c = ++b;

	
	// string containing conflicting code which we want to ignore
	const char* str = "SOME_TOKEN struct {}, enum, class \"espaces\" #include";
	const char* strs[] = {
		"one",
		"two",
		"three",
		"four"
	};
}